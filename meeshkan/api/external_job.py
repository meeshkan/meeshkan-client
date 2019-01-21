from functools import wraps
import os
from typing import Optional
import uuid
from ..core.service import Service
from ..core.api import Api

__all__ = ["create_blocking_job", "as_blocking_job"]


class ExternalJobWrapper:
    def __init__(self, job_id: uuid.UUID):
        self.job_id = job_id

    def __enter__(self):
        register_external_job(self.job_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        unregister_external_job(self.job_id)


def as_blocking_job(job_name, report_interval_secs):
    def job_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            job = create_blocking_job(name=job_name, poll_interval=report_interval_secs)
            with job:
                func(*args, *kwargs)
        return func_wrapper
    return job_decorator


def create_blocking_job(name: str, poll_interval: Optional[float] = None) -> ExternalJobWrapper:
    pid = os.getpid()
    with Service.api() as proxy:  # type: Api
        job_id = proxy.external_jobs.create_external_job(pid=pid, name=name, poll_interval=poll_interval)
        return ExternalJobWrapper(job_id=job_id)


def register_external_job(job_id: uuid.UUID):
    with Service.api() as proxy:  # type: Api
        proxy.external_jobs.register_active_external_job(job_id=job_id)


def unregister_external_job(job_id: uuid.UUID):
    with Service.api() as proxy:  # type: Api
        proxy.external_jobs.unregister_active_external_job(job_id=job_id)
