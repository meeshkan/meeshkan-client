from typing import Callable, Any

import Pyro4
import Pyro4.errors

import client.scheduler
import client.job
import client.service


@Pyro4.expose
@Pyro4.behavior(instance_mode="single")  # Singleton
class Api(object):
    """Exposed by the Pyro server for communications with the CLI."""

    def __init__(self, scheduler: client.scheduler.Scheduler, service: client.service.Service = None):
        self.scheduler = scheduler
        self.service = service
        self.__stop_callbacks = []
        self.__was_shutdown = False

    def __enter__(self):
        self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def submit(self, executable):
        job_number = self.scheduler.get_number()
        self.scheduler.submit_job(client.job.Job(executable, job_number=job_number))

    def list_jobs(self):
        return [job.to_dict() for job in self.scheduler.jobs]

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
