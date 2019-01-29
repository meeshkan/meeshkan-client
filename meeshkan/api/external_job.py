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
    """
    Mark a function as Meeshkan job: notifications are sent when the function execution begins and
    ends. If the function reports scalar values with :py:func:`meeshkan.report_scalar`, notifications are sent
    also at the given report intervals.

    The function execution blocks the calling process, i.e., execution is not scheduled to the `meeshkan` agent
    for execution.

    Example::

        @meeshkan.as_blocking_job(job_name="my-job", report_interval_secs=60)
        def train():
            # Send notification when "loss" is less than 0.8
            meeshkan.add_condition("loss", lambda v: v < 0.8)
            # Enter training loop
            for i in range(EPOCHS):
                # Compute loss
                loss = ...
                # Report loss to the Meeshkan agent
                meeshkan.report_scalar("loss", loss)

    :param job_name: Name of the job
    :param report_interval_secs: Notification report interval in seconds.
    :return: Function decorator
    """
    def job_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            job = create_blocking_job(name=job_name, report_interval_secs=report_interval_secs)
            with job:
                return func(*args, **kwargs)
        return func_wrapper
    return job_decorator


def create_blocking_job(name: str, report_interval_secs: Optional[float] = None) -> ExternalJobWrapper:
    """
    Create a blocking Meeshkan job used as context manager. The job is called blocking
    because it is not scheduled to the agent for execution. The job
    can be reused as context manager, ensuring that scalars reported earlier with :func:`meeshkan.report_scalar`
    are still included in the notifications.

    Example::

        meeshkan_job = meeshkan.create_blocking_job(name="my-job", report_interval_secs=60)
        with meeshkan_job:
            # Send notification when "loss" is less than 0.8
            meeshkan.add_condition("loss", lambda v: v < 0.8)
            # Enter training loop
            for i in range(EPOCHS):
                # Compute loss
                loss = ...
                # Report loss to the Meeshkan agent
                meeshkan.report_scalar("loss", loss)

    :param name: Name of the job
    :param report_interval_secs: Notification report interval in seconds
    :return: Meeshkan blocking job
    """
    pid = os.getpid()
    with Service.api() as proxy:  # type: Api
        job_id = proxy.external_jobs.create_external_job(pid=pid, name=name, poll_interval=report_interval_secs)
        return ExternalJobWrapper(job_id=job_id)


def register_external_job(job_id: uuid.UUID):
    with Service.api() as proxy:  # type: Api
        proxy.external_jobs.register_active_external_job(job_id=job_id)


def unregister_external_job(job_id: uuid.UUID):
    with Service.api() as proxy:  # type: Api
        proxy.external_jobs.unregister_active_external_job(job_id=job_id)
