from meeshkan.notifications.notifiers import Notifier
from meeshkan.core.job import Job

class MockResponse:
    def __init__(self, json_data=None, status_code=None):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def text(self):
        return "Mock response"

    @property
    def ok(self):
        return self.status_code == 200 or self.status_code == 400

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockNotifier(Notifier):
    def __init__(self):
        super().__init__()
        self.finished_jobs = []
        self.notified_jobs = []
        self.started_jobs = []

    def notify_job_start(self, job: Job):
        self.started_jobs.append({'job': job})

    def notify_job_end(self, job: Job):
        self.finished_jobs.append({'job': job})

    def notify(self, job: Job, image_url: str, n_iterations: int = -1, iterations_unit: str = "iterations") -> None:
        self.notified_jobs.append({'job': job})