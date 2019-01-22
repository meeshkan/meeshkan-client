from typing import Optional, List

import Pyro4

from ..core.service import Service
from ..core.job import SageMakerJob

__all__ = ["monitor"]  # type: List[str]


def monitor(job_name: str, poll_interval: Optional[float] = None):
    """
    Start monitoring a SageMaker training job. Requires the agent to be running.

    The agent periodically reads the metrics reported by the job from the SageMaker API and
    sends Meeshkan notifications.

    Requires ``sagemaker`` Python SDK to be installed. The required AWS credentials are automatically read using
    the standard
    `Boto credential chain <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html>`_.

    Example::

        job_name = "sagemaker-job"
        sagemaker_estimator.fit({'training': inputs}, job_name=job_name, wait=False)
        meeshkan.sagemaker.monitor(job_name=job_name, poll_interval=600)

    :param job_name: SageMaker training job name
    :param poll_interval: Polling interval in seconds, optional. Defaults to one hour.
    """
    with Service.api() as proxy:
        sagemaker_job = proxy.monitor_sagemaker(job_name=job_name, poll_interval=poll_interval)  # type: SageMakerJob
        if sagemaker_job.status.is_processed:
            print("Job {job_name} is already finished with status {status}.".format(job_name=sagemaker_job.name,
                                                                                    status=sagemaker_job.status.name))
        else:
            print("Started monitoring job {job_name}, "
                  "currently in phase {status}".format(job_name=sagemaker_job.name, status=sagemaker_job.status.name))
