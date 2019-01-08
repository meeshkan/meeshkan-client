"""Watch a running SageMaker job."""
from typing import Callable, Dict, List, Optional, Tuple
import logging
import uuid

import asyncio

from .job import JobStatus, SageMakerJob, BaseJob
from ..exceptions import SageMakerNotAvailableException, JobNotFoundException


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
        :param client: SageMaker client built with boto3.client("sagemaker") used for connecting to SageMaker
        """
        self.client = client
        self.sagemaker_session = sagemaker_session  # type: Optional[sagemaker.session.Session]
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

        if not self.sagemaker_session:
            try:
                import sagemaker
            except Exception:
                LOGGER.exception("Could not import sagemaker library.")
                self._error_message = "Could not import sagemaker library. Please do 'pip install sagemaker' manually."
                raise SageMakerNotAvailableException(self._error_message)
            self.sagemaker_session = sagemaker.Session(sagemaker_client=self.client)

        self.connection_succeeded = True

    @staticmethod
    def build_client_or_none():
        """
        :return: SageMaker boto3 client or None if failed
        """
        try:
            import boto3
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

    def wait_for_job_finish(self, job: SageMakerJob):
        """
        Wait for SageMaker job to finish (blocking).
        :param job:
        :raises ValueError: If job does not finish cleanly (is stopped, for example)
        :return:
        """
        self.check_or_build_connection()
        LOGGER.info("Started waiting for job %s to finish.", job.name)
        self.sagemaker_session.wait_for_job(job=job.name, poll=10)
        LOGGER.info("Job %s finished with status %s", job.name, job.status)
        job.status = self.get_job_status(job_name=job.name)


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

    def start(self, job: SageMakerJob) -> Tuple[asyncio.Task]:
        self.sagemaker_helper.check_or_build_connection()
        return self._event_loop.create_task(self.monitor(job))

    async def monitor(self, job: SageMakerJob):
        update_polling_task = self._event_loop.create_task(self.poll_updates(job))  # type: asyncio.Task
        wait_for_finish_future = \
            self._event_loop.run_in_executor(None, self.sagemaker_helper.wait_for_job_finish, job)  # type: asyncio.Future
        try:
            await wait_for_finish_future
        except ValueError:
            # Job stopped or did not finish cleanly
            LOGGER.info("Waiting for job %s ended with value error", job.name)
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Failed waiting for job to finish")
        finally:
            update_polling_task.cancel()

        job.status = self.sagemaker_helper.get_job_status(job_name=job.name)
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
