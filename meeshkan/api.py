from typing import Callable, Any, Tuple, List

import Pyro4
import Pyro4.errors

import meeshkan.scheduler
import meeshkan.job
import meeshkan.service


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")  # Singleton
class Api(object):
    """Exposed by the Pyro server for communications with the CLI."""

    def __init__(self, scheduler: meeshkan.scheduler.Scheduler, service: meeshkan.service.Service = None):
        self.scheduler = scheduler
        self.service = service
        self.__stop_callbacks = []  # type: List[Callable[[], None]]
        self.__was_shutdown = False

    def __enter__(self):
        self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def submit(self, args: Tuple[str, ...], name=None):
        job = self.scheduler.create_job(args, name)
        self.scheduler.submit_job(job)
        return job

    def list_jobs(self):
        jobs = list()
        for job in self.scheduler.jobs:
            temp_job_dict = job.to_dict()
            temp_job_dict['notifier status'] = self.scheduler.get_notification_status(job.id)
            jobs.append(temp_job_dict)
        return jobs

    def add_stop_callback(self, func: Callable[[], Any]):
        self.__stop_callbacks.append(func)

    def stop(self):
        if self.__was_shutdown:
            return
        self.__was_shutdown = True
        self.scheduler.stop()
        if self.service is not None:
            self.service.stop()
        for callback in self.__stop_callbacks:
            callback()
