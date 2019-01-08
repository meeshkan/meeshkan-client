import Pyro4

from ..core.service import Service
from ..core.job import SageMakerJob

Pyro4.config.SERIALIZER = 'dill'


def monitor(job_name: str):
    with Service().api as proxy:
        sagemaker_job = proxy.monitor_sagemaker(job_name)  # type: SageMakerJob
        print("Started monitoring job {job_name}, currently in phase {status}".format(job_name=job_name,
                                                                                      status=sagemaker_job.status.name))
        return sagemaker_job


__all__ = ["monitor"]
