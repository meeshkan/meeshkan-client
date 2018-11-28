from typing import Callable, Any, Tuple, Union, List, Optional
import logging
import uuid

import Pyro4
import Pyro4.errors

from .scheduler import Scheduler
from .service import Service
from .tasks import TaskPoller
from ..notifications.notifiers import Notifier

__all__ = ["Api"]

LOGGER = logging.getLogger(__name__)


@Pyro4.behavior(instance_mode="single")  # Singleton
class Api(object):
    """Partially xposed by the Pyro server for communications with the CLI."""

    # Private methods
    def __init__(self, scheduler: Scheduler, service: Service = None, poller: TaskPoller = None,
                 notifier: Notifier = None):
        self.scheduler = scheduler
        self.service = service
        self.task_poller = poller
        self.notifier = notifier
        self.__stop_callbacks = []  # type: List[Callable[[], None]]
        self.__was_shutdown = False

    def __enter__(self):
        self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def get_notification_status(self, job_id: uuid.UUID) -> str:
        """Returns last notification status for job_id
        """
        if self.notifier:
            # results hold a Dict[str, Optional[NotificationWithStatus]] where str is name of notifier
            results = self.notifier.get_last_notification_status(job_id)
            # Reformat for a string (dictionary has only one key in this instance)
            res_list = []
            for notifier, result in results.items():
                if result is not None:
                    notification, status = result
                    res_list.append("{notification}: {notifier}/{result}".format(notification=notification,
                                                                                 notifier=notifier, result=result.name))
            return '\n'.join(res_list)
        return ""

    # Exposed methods

    @Pyro4.expose
    async def poll(self):
        await self.scheduler.poll()

    @Pyro4.expose
    def submit(self, args: Tuple[str, ...], name=None, poll_interval=None):
        job = self.scheduler.create_job(args, name=name, poll_interval=poll_interval)
        self.scheduler.submit_job(job)
        return job

    @Pyro4.expose
    def list_jobs(self):
        jobs = list()
        for job in self.scheduler.jobs:
            temp_job_dict = job.to_dict()
            temp_job_dict['notifier status'] = self.get_notification_status(job.id)
            jobs.append(temp_job_dict)
        return jobs

    @Pyro4.expose
    def add_stop_callback(self, func: Callable[[], Any]):
        self.__stop_callbacks.append(func)

    @Pyro4.expose
    def report_scalar(self, pid, name, val):
        """Attempts to report a scalar update for process PID"""
        self.scheduler.report_scalar(pid, name, val)

    @Pyro4.expose
    def get_updates(self, job_id, recent_only=True, img=False) -> Tuple[meeshkan.HistoryByScalar, Optional[str]]:
        if not isinstance(job_id, uuid.UUID):
            job_id = uuid.UUID(job_id)
        vals, fname = self.scheduler.query_scalars(job_id, latest_only=recent_only, plot=img)
        if img:
            return vals, fname
        return vals, None

    @Pyro4.expose
    def stop(self):
        if self.__was_shutdown:
            return
        self.__was_shutdown = True
        self.scheduler.stop()
        if self.service is not None:
            self.service.stop()
        for callback in self.__stop_callbacks:
            callback()
