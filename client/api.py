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

    def __enter__(self):
        self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def submit(self, executable):
        job_number = self.scheduler.get_number()
        self.scheduler.submit_job(client.job.Job(executable, job_number=job_number))

    def list_jobs(self):
        return [str(job) for job in  self.scheduler.jobs]

    def stop(self):
        self.scheduler.stop()
        if self.service is not None:
            self.service.stop()
