"""Watch a running SageMaker job."""
from typing import List, Optional
import logging

import asyncio

import boto3

from .job import JobStatus, SageMakerJob, BaseJob
from ..exceptions import SageMakerNotAvailableException, JobNotFoundException


LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class BaseJobMonitor:
    def __init(self):
        pass

    async def monitor(self, job: BaseJob):
        raise NotImplementedError


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


class SageMakerJobMonitor(BaseJobMonitor):
    def __init__(self,
                 event_loop=None,
                 sagemaker_helper: Optional[SageMakerHelper] = None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = event_loop or asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or SageMakerHelper()  # type: SageMakerHelper
        self.tasks = []  # type: List[asyncio.Task]

    def start(self, job: BaseJob) -> asyncio.Task:
        task = self._event_loop.create_task(self.monitor(job))
        self.tasks.append(task)
        return task

    async def monitor(self, job: BaseJob):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs.")

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

            LOGGER.info("Stopped monitoring job %s", job.name)
            # TODO Notify finish
        except asyncio.CancelledError:
            LOGGER.debug("Job tracking cancelled for job %s", job.name)

    def create_job(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
