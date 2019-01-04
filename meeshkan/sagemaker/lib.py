from ..core.service import Service


def monitor(job_name: str):
    with Service().api as proxy:
        proxy.monitor_sagemaker(job_name)


__all__ = ["monitor"]
