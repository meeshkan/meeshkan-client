from typing import Optional, List

import Pyro4

from ..core.service import Service
from ..core.job import SageMakerJob

__all__ = ["monitor"]  # type: List[str]

Pyro4.config.SERIALIZER = 'dill'


def monitor(job_name: str, poll_interval: Optional[float] = None):
    """
    Start monitoring a SageMaker training job.

    :param job_name: SageMaker training job name
    :param poll_interval: Polling interval in seconds, optional. Defaults to one hour.
    :return: SageMakerJob instance
    """
    with Service().api as proxy:
        sagemaker_job = proxy.monitor_sagemaker(job_name=job_name, poll_interval=poll_interval)  # type: SageMakerJob
        if sagemaker_job.status.is_processed:
            print("Job {job_name} is already finished with status {status}.".format(job_name=sagemaker_job.name,
                                                                                    status=sagemaker_job.status.name))
        else:
            print("Started monitoring job {job_name}, "
                  "currently in phase {status}".format(job_name=sagemaker_job.name, status=sagemaker_job.status.name))
        return sagemaker_job
