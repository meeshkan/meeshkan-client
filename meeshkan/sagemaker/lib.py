import Pyro4

from ..core.service import Service
from ..core.job import SageMakerJob

Pyro4.config.SERIALIZER = 'dill'


def monitor(job_name: str):
    with Service().api as proxy:
        sagemaker_job = proxy.monitor_sagemaker(job_name)  # type: SageMakerJob
        if sagemaker_job.status.is_processed:
            print("Job {job_name} is already finished with status {status}.".format(job_name=sagemaker_job.name,
                                                                                    status=sagemaker_job.status.name))
        else:
            print("Started monitoring job {job_name}, "
                  "currently in phase {status}".format(job_name=sagemaker_job.name, status=sagemaker_job.status.name))
        return sagemaker_job


__all__ = ["monitor"]
