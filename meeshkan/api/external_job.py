from functools import wraps
import os
from typing import Optional
import uuid
from ..core.service import Service

__all__ = ["create_external_job", "as_job"]


class ExternalJobWrapper:
    def __init__(self, job_id: uuid.UUID):
        self.job_id = job_id

    def __enter__(self):
        # Register active job in the agent
        register_external_job(self.job_id)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Unregister active job
        unregister_external_job(self.job_id)


def tags(tag_name):
    def tags_decorator(func):
        @wraps(func)
        def func_wrapper(name):
            return "<{0}>{1}</{0}>".format(tag_name, func(name))
        return func_wrapper
    return tags_decorator


def as_job(job_name, report_interval):
    def job_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            job = create_external_job(name=job_name, poll_interval=report_interval)
            with job:
                func(*args, *kwargs)
        return func_wrapper
    return job_decorator


def create_external_job(name: str, poll_interval: Optional[float] = None) -> ExternalJobWrapper:
    pid = os.getpid()
    with Service.api() as proxy:
        job_id = proxy.create_external_job(pid=pid, name=name, poll_interval=poll_interval)
        return ExternalJobWrapper(job_id=job_id)


def register_external_job(job_id: uuid.UUID):
    pid = os.getpid()
    with Service.api() as proxy:
        proxy.register_active_external_job(job_id=job_id)


def unregister_external_job(job_id: uuid.UUID):
    with Service.api() as proxy:
        proxy.unregister_active_external_job(job_id=job_id)
