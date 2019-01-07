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


class LazyCache:
    def __init__(self, func):
        self.func = func
        self.value = None

    def __call__(self):
        if self.value is None:
            self.value = self.func()
        return self.value


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

        :param client: SageMaker client built with boto3.client("sagemaker"). If not given,
        it is tried to be built safely.
        """
        if client:
            self.client = client
        else:
            try:
                self.client = SageMakerHelper.build_client()
            except Exception:  # pylint-disable:broad-except
                self.client = None

    @property
    def enabled(self):
        return self.client is not None

    @staticmethod
    def build_client():
        """
        :raises: SageMakerNotAvailableException if building the client fails
        :return: SageMaker boto3 client
        """
        try:
            return boto3.client("sagemaker")
        except Exception:
            raise SageMakerNotAvailableException

    def check_available(self):
        """
        Check that SageMaker is available by calling API
        :raises SageMakerNotAvailableException if client cannot be built or SageMaker APIs are not reachable
        :return: None if APIs could be called without exceptions
        """
        if not self.enabled:
            raise SageMakerNotAvailableException

        try:
            self.client.list_training_jobs()
        except Exception:
            raise SageMakerNotAvailableException

    def get_job_status(self, job_name) -> JobStatus:
        """
        :param job_name: Name of the SageMaker training job
        :raises JobNotFoundException
        :return: Job status
        """
        if not self.enabled:
            raise SageMakerNotAvailableException

        try:
            training_job = self.client.describe_training_job(TrainingJobName=job_name)
            status = training_job['TrainingJobStatus']
            return SageMakerHelper.SAGEMAKER_STATUS_TO_JOB_STATUS[status]
        except self.client.exceptions.ClientError:
            raise JobNotFoundException


@LazyCache
def get_sagemaker_helper():
    return SageMakerHelper(client=boto3.client("sagemaker"))


class BaseJobMonitor:
    def __init(self):
        pass

    async def monitor(self, job: BaseJob, poll_time: float):
        raise NotImplementedError


class SageMakerJobMonitor(BaseJobMonitor):
    def __init__(self,
                 sagemaker_helper: Optional[SageMakerHelper]=None):
        super().__init__()
        # self._notify = notify_function
        self._event_loop = asyncio.get_event_loop()
        self.sagemaker_helper = sagemaker_helper or get_sagemaker_helper()  # type: SageMakerHelper

    def start(self, job: BaseJob):
        self._event_loop.create_task(self.monitor(job, poll_time=job.poll_time))

    async def monitor(self, job: BaseJob, poll_time: float):
        if not isinstance(job, SageMakerJob):
            raise RuntimeError("SageMakerJobMonitor can only monitor SageMakerJobs")

        LOGGER.debug("Starting SageMaker job tracking for job %s", job.name)
        sleep_time = poll_time
        try:
            while True:
                status = self.sagemaker_helper.get_job_status(job.name)
                # TODO Add new scalars with `sagemaker_job.add_scalar_to_history()`
                # TODO Notify updates with `self._notify(sagemaker_job)`
                # TODO Change to status.is_processed when merged
                if status == JobStatus.FINISHED or status == JobStatus.FAILED or JobStatus.CANCELLED_BY_USER:
                    break

                await asyncio.sleep(sleep_time)  # Let other tasks run meanwhile
            # TODO Notify finish
            # self._notify_end(job_name)  # Synchronously notify of changes.
        except asyncio.CancelledError:
            LOGGER.debug("Job tracking cancelled for job %s", job.name)

    def create_job(self, job_name: str) -> SageMakerJob:
        sagemaker_helper = self.sagemaker_helper
        sagemaker_helper.check_available()
        status = sagemaker_helper.get_job_status(job_name)
        return SageMakerJob(sagemaker_helper=sagemaker_helper,
                            job_name=job_name,
                            status=status)
