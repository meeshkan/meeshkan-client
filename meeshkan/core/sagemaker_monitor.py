"""Watch a running SageMaker job."""
from typing import Callable, List, Optional
import logging

import asyncio

from .job import JobStatus, SageMakerJob, BaseJob
from ..exceptions import SageMakerNotAvailableException, JobNotFoundException, DeferredImportException

try:
    # Just in case we make boto3 dependency optional
    import boto3
except ImportError as ex:
    boto3 = DeferredImportException(ex)

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

    def __init__(self, client=None):
        """
        Init SageMaker helper in the disabled state.
        :param client: SageMaker client built with boto3.client("sagemaker") used for connecting to SageMaker
        """
        self.client = client
        self.connection_tried = False
        self.connection_succeeded = False
        self._error_message = None  # type: Optional[str]

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


class SageMakerJobMonitor:
    def __init__(self,
                 event_loop=None,
                 sagemaker_helper: Optional[SageMakerHelper] = None,
                 notify_start: Optional[Callable[[SageMakerJob], None]] = None,
                 notify_finish: Optional[Callable[[SageMakerJob], None]] = None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = event_loop or asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or SageMakerHelper()  # type: SageMakerHelper
        self.notify_start = notify_start  # type: Optional[Callable[[SageMakerJob], None]]
        self.notify_finish = notify_finish  # type: Optional[Callable[[SageMakerJob], None]]

    def start(self, job: SageMakerJob) -> asyncio.Task:
        self.sagemaker_helper.check_or_build_connection()
        # TODO Check that job exists
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
            job.status = self.sagemaker_helper.get_job_status(job_name=job)
        finally:
            update_polling_task.cancel()

        job.status = job_status
        if self.notify_finish:
            self.notify_finish(job)

    async def poll_updates(self, job: BaseJob):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs.")

        if job.status.is_processed:
            LOGGER.info("SageMaker job %s already finished, returning", job.name)
            return

        LOGGER.debug("Starting SageMaker job tracking for job %s with polling interval %f", job.name, job.poll_time)
        sleep_time = job.poll_time
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
                if job.status.is_processed:
                    break

                await asyncio.sleep(sleep_time)

            LOGGER.info("Stopped monitoring SageMakerJob %s, got status %s", job.name, job.status)
        except asyncio.CancelledError:
            LOGGER.debug("SageMakerJob tracking cancelled for job %s", job.name)

    def create_job(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
