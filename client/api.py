import Pyro4
from .scheduler import Scheduler
from .job import Job, ProcessExecutable


@Pyro4.expose
class Api(object):

    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler

    # noinspection PyMethodMayBeStatic
    def test(self, name):
        return "Hello " + name

    def submit(self, script_name):
        executable = ProcessExecutable.from_str(script_name)
        job_id = self.scheduler.get_id()
        self.scheduler.submit_job(Job(executable, job_id))

    def list_jobs(self):
        return [str(job) for job in  self.scheduler.submitted_jobs]
