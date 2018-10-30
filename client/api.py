import Pyro4
import Pyro4.errors
from scheduler import Scheduler
from job import Job, ProcessExecutable


class Api(object):
    """
    Exposed by the Pyro server for communications with the CLI.
    """

    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler

    def submit(self, script_name):
        executable = ProcessExecutable.from_str(script_name)
        job_id = self.scheduler.get_id()
        self.scheduler.submit_job(Job(executable, job_id))

    def list_jobs(self):
        return [str(job) for job in  self.scheduler.jobs]

    def terminate_daemon(self):
        try:
            self.scheduler.terminate_daemon()
        except Pyro4.errors.ConnectionClosedError:  # This is expected
            print("Daemon shutdown")
