import Pyro4

from ..core.service import Service

Pyro4.config.SERIALIZER = 'dill'


def monitor(job_name: str):
    with Service().api as proxy:
        return proxy.monitor_sagemaker(job_name)


__all__ = ["monitor"]
