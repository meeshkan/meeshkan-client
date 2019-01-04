import boto3
from ..core.service import Service


class LazyCache():
    def __init__(self, func):
        self.func = func
        self.value = None

    def __call__(self, *args):
        if not self.value:
            self.value = self.func(*args)
        return self.value


@LazyCache
def client():
    print("Building sagemaker client")
    return boto3.client("sagemaker")


def monitor(job_name: str):
    sagemaker = client()
    print(sagemaker.describe_training_job(TrainingJobName=job_name))
    with Service().api as proxy:
        proxy.monitor_sagemaker(job_name)


__all__ = ["monitor"]
