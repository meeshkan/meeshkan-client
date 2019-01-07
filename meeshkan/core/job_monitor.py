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
        Tries to verify SageMaker connection at construction time. If connecting to SageMaker APIs fails,
        helper remains in disabled state. Trying to access APIs afterwards raises
        SageMakerNotAvailableException.
        :param client: SageMaker client built with boto3.client("sagemaker"). If not given,
        it is tried to be built safely.
        """
        self.client = client if client is not None else SageMakerHelper.build_client_or_none()
        self.enabled = self.check_sagemaker_connection() if self.client is not None else False

    @property
    def __has_client(self):
        return self.client is not None

    @staticmethod
    def build_client_or_none():
        """
        :return: SageMaker boto3 client or None if failed
        """
        try:
            return boto3.client("sagemaker")
        except Exception:
            return None

    def check_sagemaker_connection(self) -> bool:
        """
        Check that SageMaker is available by checking that the client exists and calling SageMaker API
        :return: True if API could be called without exceptions, otherwise False
        """
        if not self.__has_client:
            return False

        try:
            self.client.list_training_jobs()
            LOGGER.info("SageMaker client successfully verified.")
            return True
        except Exception as ex:  # pylint:disable=broad-except
            LOGGER.info("Could not verify SageMaker connection: %o", ex)

        return False

    def __verify_connection(self):
        """
        Check that SageMaker connection exists.
        :raises SageMakerNotAvailableException: If no connection to SageMaker.
        :return:
        """
        if not self.enabled:
            if self.__has_client:
                message = "Could not connect to SageMaker. Please check your authorization."
            else:
                message = "Could not build boto3 client. Please check your AWS credentials."
            raise SageMakerNotAvailableException(message)

    def get_job_status(self, job_name) -> JobStatus:
        """
        Get job status from SageMaker API. Use this to start monitoring jobs and to check they exist.
        :param job_name: Name of the SageMaker training job
        :raises SageMakerNotAvailableException:
        :raises JobNotFoundException: If job was not found.
        :return: Job status
        """

        self.__verify_connection()

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
        return SageMakerJob(sagemaker_helper=sagemaker_helper,
                            job_name=job_name,
                            status=status,
                            poll_interval=poll_interval)
