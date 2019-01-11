"""Watch a running SageMaker job."""
import asyncio
from typing import Any, Callable, List, Optional
import logging

import pandas as pd

from .job import JobStatus, SageMakerJob, BaseJob
from ..exceptions import SageMakerNotAvailableException, JobNotFoundException, DeferredImportException

try:
    # Just in case we make boto3 dependency optional
    import boto3
except ImportError as ex:
    boto3 = DeferredImportException(ex)

try:
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
        except Exception:
            return None

    def get_job_status(self, job_name) -> JobStatus:
        """
        Get job status from SageMaker API. Use this to start monitoring jobs and to check they exist.
        :param job_name: Name of the SageMaker training job
        :raises SageMakerNotAvailableException:
        :raises JobNotFoundException: If job was not found.
        :return: Job status
        """

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
        self.check_or_build_connection()

        LOGGER.debug("Checking for updates for job %s", job_name)
        analytics = sagemaker.analytics.TrainingJobAnalytics(training_job_name=job_name,
                                                             sagemaker_session=self.sagemaker_session)
        return analytics.dataframe(force_refresh=True)


class SageMakerJobMonitor:
    MINIMUM_POLLING_INTERVAL_SECS = 60

    def __init__(self,
                 event_loop=None,
                 sagemaker_helper: Optional[SageMakerHelper] = None,
                 notify_start: Optional[Callable[[BaseJob], Any]] = None,
                 notify_finish: Optional[Callable[[BaseJob], Any]] = None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = event_loop or asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or SageMakerHelper()  # type: SageMakerHelper
        self.notify_start = notify_start  # type: Optional[Callable[[SageMakerJob], None]]
        self.notify_finish = notify_finish  # type: Optional[Callable[[SageMakerJob], None]]

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
        except Exception:  # pylint:disable=broad-except
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

    @staticmethod
    def get_new_records(df_new: pd.DataFrame, df_old: Optional[pd.DataFrame] = None):
        """
        Return a list of new records
        :param df_new: New dataframe, should have the same rows as `df_old` plus any new records
        :param df_old: Old dataframe, can be left None to return all records of the new DataFrame
        :return: List of dictionaries of the form {'column' -> 'value'}
        """
        if df_old is None:
            return df_new.to_dict(orient='records')

        assert len(df_new) >= len(df_old)
        return df_new.loc[len(df_old):len(df_new)].to_dict(orient='records')

    async def poll_updates(self, job: BaseJob):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs.")

        if job.status.is_processed:
            LOGGER.info("SageMaker job %s already finished, returning", job.name)
            return

        sleep_time = max(job.poll_time, SageMakerJobMonitor.MINIMUM_POLLING_INTERVAL_SECS)
        LOGGER.debug("Starting SageMaker job tracking for job %s with polling interval of %f seconds.",
                     job.name, sleep_time)
        previous_metrics_df = None

        if not job.status.is_launched and self.notify_start:
            self.notify_start(job)

        try:
            while True:
                LOGGER.debug("Checking updates for job %s", job.name)
                previous_status = job.status
                job.status = self.sagemaker_helper.get_job_status(job.name)
                LOGGER.debug("Job %s: previous status %s, current status %s", job.name, previous_status, job.status)
                if not previous_status.is_launched and job.status.is_launched and self.notify_start:
                    self.notify_start(job)

                # TODO Add new scalars with `sagemaker_job.add_scalar_to_history()`
                # TODO Notify updates with `self._notify(sagemaker_job)`

                try:
                    metrics_df = await self._event_loop.run_in_executor(
                        None,
                        self.sagemaker_helper.get_training_job_analytics_df, job.name)
                    if not metrics_df.empty:
                        new_records = SageMakerJobMonitor.get_new_records(df_new=metrics_df, df_old=previous_metrics_df)
                        previous_metrics_df = metrics_df
                    else:
                        new_records = []

                    LOGGER.debug("Got new metric records: %s", new_records)
                    for record in new_records:
                        # TODO Handle metric_name.lower() == 'epoch'?
                        job.add_scalar_to_history(scalar_name=record['metric_name'], scalar_value=record['value'])
                except Exception as ex:  # pylint:disable=broad-except
                    if isinstance(ex, asyncio.CancelledError):
                        raise ex
                    LOGGER.exception("Checking for SageMaker job metrics failed, ignoring.")

                if job.status.is_processed:
                    break

                await asyncio.sleep(sleep_time)

            LOGGER.info("Stopped monitoring SageMakerJob %s, got status %s", job.name, job.status)
        except asyncio.CancelledError:
            LOGGER.debug("SageMakerJob tracking cancelled for job %s", job.name)
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Polling for updates failed")
            # Ignore

    def create_job(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
