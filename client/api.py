import Pyro4
from .scheduler import Scheduler
from .job import Job, ProcessExecutable


@Pyro4.expose
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
        return [str(job) for job in  self.scheduler.submitted_jobs]
