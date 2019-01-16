"""Watch a running SageMaker job."""
import asyncio
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
import os
import threading

import pandas as pd

from .job import JobStatus, SageMakerJob, BaseJob
from ..exceptions import SageMakerNotAvailableException, JobNotFoundException, DeferredImportException

try:
    # Just in case we make boto3 dependency optional
    import boto3
except ImportError as ex:
    boto3 = DeferredImportException(ex)

try:
    # Sagemaker Python SDK is optional
    import sagemaker
except ImportError as ex:
    sagemaker = DeferredImportException(ex)


LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class SageMakerHelper:
    SAGEMAKER_STATUS_TO_JOB_STATUS = {
        "InProgress": JobStatus.RUNNING,
        "Completed": JobStatus.FINISHED,
        "Failed": JobStatus.FAILED,
        "Stopping": JobStatus.RUNNING,  # TODO Create status for this?
        "Stopped": JobStatus.CANCELLED_BY_USER
    }

    def __init__(self, client=None, sagemaker_session=None):
        """
        Init SageMaker helper in the disabled state.
        :param client: SageMaker client built with boto3.client("sagemaker") used for low-level connections to SM API
        :param sagemaker_session: SageMaker Python SDK session
        """
        self.client = client
        self.connection_tried = False
        self.connection_succeeded = False
        self._error_message = None  # type: Optional[str]
        self.sagemaker_session = sagemaker_session
        self.lock = threading.Lock()
        self.analytics_by_job_name = {}  # type: Dict[str, sagemaker.analytics.TrainingJobAnalytics]

    @property
    def __has_client(self):
        return self.client is not None

    def check_or_build_connection(self):
        """
        Check that SageMaker connection exists. Tries to create if not yet attempted.
        ALWAYS call this before attempting to access SageMaker.
        :raises SageMakerNotAvailableException: If connection to SageMaker cannot be established.
        :return:
        """
        if self.connection_tried:
            if self.connection_succeeded:
                return
            if not self.connection_succeeded:
                raise SageMakerNotAvailableException(message=self._error_message or None)

        self.connection_tried = True

        self.client = self.client or SageMakerHelper.build_client_or_none()

        if not self.client:
            self._error_message = "Could not create boto client. Check your credentials"
            raise SageMakerNotAvailableException(self._error_message)

        self.sagemaker_session = self.sagemaker_session or sagemaker.session.Session(sagemaker_client=self.client)

        try:
            self.client.list_training_jobs()
            LOGGER.info("SageMaker client successfully verified.")
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Could not verify SageMaker connection")
            self._error_message = "Could not connect to SageMaker. Check your authorization."
            raise SageMakerNotAvailableException(self._error_message)

        self.connection_succeeded = True

    @staticmethod
    def build_client_or_none():
        """
        :return: SageMaker boto3 client or None if failed
        """
        try:
            return boto3.client("sagemaker")
        except Exception:  # pylint: disable=broad-except
            return None

    def get_job_status(self, job_name) -> JobStatus:
        """
        Get job status from SageMaker API. Use this to start monitoring jobs and to check they exist.
        :param job_name: Name of the SageMaker training job
        :raises SageMakerNotAvailableException:
        :raises JobNotFoundException: If job was not found.
        :return: Job status
        """
        with self.lock:
            self.check_or_build_connection()

        try:
            training_job = self.client.describe_training_job(TrainingJobName=job_name)
        except self.client.exceptions.ClientError:
            raise JobNotFoundException

        status = training_job['TrainingJobStatus']
        return SageMakerHelper.SAGEMAKER_STATUS_TO_JOB_STATUS[status]

    def wait_for_job_finish(self, job_name: str) -> JobStatus:
        """
        Wait for SageMaker job to finish (blocking).
        :param job_name: SageMaker training job name
        :raises Exception: If job does not finish cleanly (is stopped, for example) or waiting took too long
        :return JobStatus: Job status after waiting
        """
        with self.lock:
            self.check_or_build_connection()
        LOGGER.info("Started waiting for job %s to finish.", job_name)
        waiter = self.client.get_waiter('training_job_completed_or_stopped')
        attempt_delay_secs = 60
        max_attempts = 60 * 24 * 3  # Three days
        waiter.wait(
            TrainingJobName=job_name,
            WaiterConfig={
                'Delay': attempt_delay_secs,
                'MaxAttempts': max_attempts  # TODO Wait longer?
            }
        )
        job_status = self.get_job_status(job_name=job_name)
        LOGGER.info("Job %s finished with status %s", job_name, job_status)

        if not job_status.is_processed and not job_status.stale:
            waited_hours = max_attempts * attempt_delay_secs / 3600
            LOGGER.exception("Exited waiter after waiting %f hours", waited_hours)
            raise RuntimeError("Did not expect to wait for more than {hours} hours".format(hours=waited_hours))
        return job_status

    def get_training_job_analytics_df(self, job_name: str):
        with self.lock:
            self.check_or_build_connection()

        LOGGER.debug("Checking for updates for job %s", job_name)
        analytics = self.analytics_by_job_name.setdefault(job_name,
                                                          sagemaker.analytics.TrainingJobAnalytics(
                                                              training_job_name=job_name,
                                                              sagemaker_session=self.sagemaker_session))
        return analytics.dataframe(force_refresh=True)


class JobScalarHelper:

    def __init__(self, job: BaseJob):
        self.job = job
        self.last_timestamp_by_metric = {}  # type: Dict[str, float]

    def add_new_scalars_from(self, metrics_dataframe: pd.DataFrame) -> bool:
        """
        Add all new records from `metrics_dataframe` to job scalar history, keeping track of the previously
        seen maximum timestamp. It is assumed that for a given metric, all new records have timestamps larger than
        the previously seen maximum timestamp.
        :param metrics_dataframe: DataFrame with records with names "metric_name", "value", "timestamp"
        :return: Boolean denoting if new values were added to job scalar history
        """
        metrics_grouped_by_name = metrics_dataframe.groupby(by="metric_name")

        added_new_metrics = False

        for metric_name, metrics_for_name in metrics_grouped_by_name:
            max_timestamp_for_name = metrics_for_name["timestamp"].max()
            previous_last_timestamp_or_none = self.last_timestamp_by_metric.get(metric_name, float("-inf"))

            new_records_df = metrics_for_name[metrics_for_name.timestamp > previous_last_timestamp_or_none]

            for _, record in new_records_df.iterrows():
                added_new_metrics = True
                self.job.add_scalar_to_history(scalar_name=record['metric_name'], scalar_value=record['value'])

            self.last_timestamp_by_metric[metric_name] = max_timestamp_for_name
        return added_new_metrics


class SageMakerJobMonitor:
    MINIMUM_POLLING_INTERVAL_SECS = 60

    def __init__(self,
                 event_loop=None,
                 sagemaker_helper: Optional[SageMakerHelper] = None,
                 notify_start: Optional[Callable[[BaseJob], Any]] = None,
                 notify_update: Optional[Callable[[BaseJob, str, int, Optional[str]], Any]] = None,
                 notify_finish: Optional[Callable[[BaseJob], Any]] = None,
                 scalar_helper_factory: Optional[Callable[[BaseJob], JobScalarHelper]] = None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = event_loop or asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or SageMakerHelper()  # type: SageMakerHelper
        self.notify_start = notify_start
        self.notify_finish = notify_finish
        self.notify_update = notify_update
        self.job_scalar_helper_factory = scalar_helper_factory or JobScalarHelper

    def start(self, job: SageMakerJob) -> asyncio.Task:
        self.sagemaker_helper.check_or_build_connection()
        return self._event_loop.create_task(self.monitor(job))

    async def monitor(self, job: SageMakerJob):
        update_polling_task = self._event_loop.create_task(self.poll_updates(job))  # type: asyncio.Task
        wait_for_finish_future = \
            self._event_loop.run_in_executor(
                None, self.sagemaker_helper.wait_for_job_finish, job.name)
        try:
            job_status = await wait_for_finish_future
        except Exception as ex:  # pylint:disable=broad-except
            if isinstance(ex, asyncio.CancelledError):
                raise ex
            LOGGER.exception("Failed waiting for job to finish")
            job_status = self.sagemaker_helper.get_job_status(job_name=job)
        finally:
            if not update_polling_task.done():
                LOGGER.info("Canceling polling for job %s", job.name)
                try:
                    update_polling_task.cancel()
                except Exception:  # pylint:disable=broad-except
                    LOGGER.exception("Canceling the task failed")

        job.status = job_status
        if self.notify_finish:
            LOGGER.info("Notifying finish for job %s with status %s", job.name, job.status)
            self.notify_finish(job)

    async def poll_updates(self, job: BaseJob):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs.")

        if job.status.is_processed:
            LOGGER.info("SageMaker job %s already finished, returning", job.name)
            return

        sleep_time = max(job.poll_time, SageMakerJobMonitor.MINIMUM_POLLING_INTERVAL_SECS)
        LOGGER.debug("Starting SageMaker job tracking for job %s with polling interval of %f seconds.",
                     job.name, sleep_time)

        if job.status.is_launched and self.notify_start:
            self.notify_start(job)

        job_scalar_helper = self.job_scalar_helper_factory(job)

        try:
            while True:
                await self.check_and_apply_updates(job=job, job_scalar_helper=job_scalar_helper)

                if job.status.is_processed:
                    break

                await asyncio.sleep(sleep_time)

            LOGGER.info("Stopped monitoring SageMakerJob %s, got status %s", job.name, job.status)
        except asyncio.CancelledError:
            LOGGER.debug("SageMakerJob tracking cancelled for job %s", job.name)
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Polling for updates failed")
            # Ignore

    async def check_and_apply_updates(self, job: BaseJob, job_scalar_helper: JobScalarHelper):
        LOGGER.debug("Checking updates for job %s", job.name)
        previous_status = job.status
        job.status = await self._event_loop.run_in_executor(None, self.sagemaker_helper.get_job_status, job.name)
        LOGGER.debug("Job %s: previous status %s, current status %s", job.name, previous_status, job.status)
        if not previous_status.is_launched and job.status.is_launched and self.notify_start:
            self.notify_start(job)

        added_new_scalars = False

        try:
            get_training_job_analytics = partial(self.sagemaker_helper.get_training_job_analytics_df, job_name=job.name)
            metrics_df = await self._event_loop.run_in_executor(None, get_training_job_analytics)
            if not metrics_df.empty:
                added_new_scalars = job_scalar_helper.add_new_scalars_from(metrics_df)
        except Exception as ex:  # pylint:disable=broad-except
            # Reading TrainingJobAnalytics routinely throws an exception, handle it here
            # TODO Only catch a more specific exception to avoid getting into failure loop?
            if isinstance(ex, asyncio.CancelledError):
                raise ex
            LOGGER.exception("Checking for SageMaker job metrics failed, ignoring.")

        if added_new_scalars:
            # Something new to report
            self._event_loop.run_in_executor(None, self.__query_and_report, job)

    # TODO Remove duplicate code with Scheduler
    def query_scalars(self, *names: Tuple[str, ...], job, latest_only: bool = True, plot: bool = False):
        if not job:
            raise JobNotFoundException(job_id=str(job.id))
        return job.get_updates(*names, plot=plot, latest=latest_only)

    def __query_and_report(self, job):
        if self.notify_update:
            # Get updates; TODO - vals should be reported once we update schema...
            vals, imgpath = self.query_scalars(job=job, latest_only=True, plot=True)
            if vals:  # Only send updates if there exists any updates
                self.notify_update(job, imgpath, n_iterations=-1)
            if imgpath is not None:
                os.remove(imgpath)

    def create_job(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
