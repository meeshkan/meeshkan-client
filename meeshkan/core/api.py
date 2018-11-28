from typing import Callable, Any, Tuple, List, Optional
import logging
import uuid

import Pyro4
import Pyro4.errors

from .scheduler import Scheduler
from .service import Service
from ..__types__ import HistoryByScalar

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]

LOGGER = logging.getLogger(__name__)


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")  # Singleton
class Api(object):
    """Exposed by the Pyro server for communications with the CLI."""

    def __init__(self, scheduler: Scheduler, service: Service = None):
        self.scheduler = scheduler
        self.service = service
        self.__stop_callbacks = []  # type: List[Callable[[], None]]
        self.__was_shutdown = False

    def __enter__(self):
        self.scheduler.start()
        return self

    async def poll(self):
        await self.scheduler.poll()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def submit(self, args: Tuple[str, ...], name=None, poll_interval=None):
        job = self.scheduler.create_job(args, name=name, poll_interval=poll_interval)
        self.scheduler.submit_job(job)
        return job

    def list_jobs(self):
        if self.scheduler.supports_notifications:
            jobs = list()
            for job in self.scheduler.jobs:
                temp_job_dict = job.to_dict()
                temp_job_dict['notifier status'] = self.scheduler.get_notification_status(job.id)
                jobs.append(temp_job_dict)
            return jobs
        return [job.to_dict() for job in self.scheduler.jobs]

    def add_stop_callback(self, func: Callable[[], Any]):
        self.__stop_callbacks.append(func)

    def report_scalar(self, pid, name, val):
        """Attempts to report a scalar update for process PID"""
        self.scheduler.report_scalar(pid, name, val)

    def get_updates(self, job_id, recent_only=True, img=False) -> Tuple[HistoryByScalar, Optional[str]]:
        if not isinstance(job_id, uuid.UUID):
            job_id = uuid.UUID(job_id)
        vals, fname = self.scheduler.query_scalars(job_id, latest_only=recent_only, plot=img)
        if img:
            return vals, fname
        return vals, None

    def stop(self):
        if self.__was_shutdown:
            return
        self.__was_shutdown = True
        self.scheduler.stop()
        if self.service is not None:
            self.service.stop()
        for callback in self.__stop_callbacks:
            callback()
