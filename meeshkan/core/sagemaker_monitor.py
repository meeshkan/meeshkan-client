"""Watch a running SageMaker job."""
from typing import Callable, Dict, List, Optional
import logging
import uuid

import asyncio
import boto3
import sagemaker

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

    @property
    def __has_client(self):
        return self.client is not None

    def _check_connection(self):
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
                raise SageMakerNotAvailableException

        self.connection_tried = True

        self.client = self.client or SageMakerHelper.build_client_or_none()

        if not self.client:
            raise SageMakerNotAvailableException("Could not create boto client. Check your credentials")

        try:
            self.client.list_training_jobs()
            LOGGER.info("SageMaker client successfully verified.")
            if not self.sagemaker_session:
                self.sagemaker_session = sagemaker.Session(sagemaker_client=self.client)
            self.connection_succeeded = True
        except Exception:  # pylint:disable=broad-except
            LOGGER.info("Could not verify SageMaker connection")
            self.connection_succeeded = False
            raise SageMakerNotAvailableException("Could not connect to SageMaker. Check your authorization.")

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

        self._check_connection()

        try:
            training_job = self.client.describe_training_job(TrainingJobName=job_name)
        except self.client.exceptions.ClientError:
            raise JobNotFoundException

        status = training_job['TrainingJobStatus']
        return SageMakerHelper.SAGEMAKER_STATUS_TO_JOB_STATUS[status]

    async def wait_for_job_finish(self, job: SageMakerJob):
        LOGGER.info("Started waiting for job %s to finish.", job.name)
        self.sagemaker_session.wait_for_job(job=job.name)
        LOGGER.info("Job %s finished with status %s", job.name, job.status)


class SageMakerJobMonitor:
    def __init__(self,
                 event_loop=None,
                 sagemaker_helper: Optional[SageMakerHelper] = None,
                 notify_finish: Optional[Callable[[SageMakerJob], None]] = None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = event_loop or asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or SageMakerHelper()  # type: SageMakerHelper
        self.tasks_by_job_id = {}  # type: Dict[uuid.UUID, asyncio.Task]
        self.notify_finish = notify_finish

    def start(self, job: SageMakerJob) -> Optional[asyncio.Task]:
        update_polling_task = self._event_loop.create_task(self.monitor(job))
        self.tasks_by_job_id[job.id] = update_polling_task
        wait_for_finish_task = self._event_loop.create_task(self.wait_for_finish(job))
        return update_polling_task, wait_for_finish_task

    async def wait_for_finish(self, job: SageMakerJob):
        await self.sagemaker_helper.wait_for_job_finish(job)
        if self.notify_finish:
            self.notify_finish(job)
        # Cancel polling for updates
        self.tasks_by_job_id[job.id].cancel()

    async def monitor(self, job: BaseJob):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs.")

        if job.status.is_processed:
            LOGGER.info("SageMaker job %s already finished, returning", job.name)
            return

        LOGGER.debug("Starting SageMaker job tracking for job %s", job.name)
        sleep_time = job.poll_time
        try:
            while True:
                LOGGER.info("Starting monitoring job %s", job.name)
                job.status = self.sagemaker_helper.get_job_status(job.name)
                # TODO Add new scalars with `sagemaker_job.add_scalar_to_history()`
                # TODO Notify updates with `self._notify(sagemaker_job)`
                if job.status.is_processed:
                    break

                await asyncio.sleep(sleep_time)

            LOGGER.info("Stopped monitoring SageMakerJob %s", job.name)
            self.notify_finish(job)
            # TODO Notify finish
        except asyncio.CancelledError:
            LOGGER.debug("SageMakerJob tracking cancelled for job %s", job.name)

    def create_job(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
