import time
from meeshkan.notifications.notifiers import Notifier
from meeshkan.core.job import Job

FUTURE_TIMEOUT = 10  # In seconds

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
        return self.status_code == 200

    def raise_for_status(self):
        raise RuntimeError("Raised for status {status}".format(status=self.status_code))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def for_unauthenticated():
        return MockResponse({"errors": [{"extensions": {"code": "UNAUTHENTICATED"}}]}, 200)


class MockNotifier(Notifier):
    def __init__(self):
        super().__init__()
        self.finished_jobs = []
        self.notified_jobs = []
        self.started_jobs = []

    def _notify_job_start(self, job: Job):
        self.started_jobs.append({'job': job})

    def _notify_job_end(self, job: Job):
        self.finished_jobs.append({'job': job})

    def _notify(self, job: Job, image_url: str, n_iterations: int = -1, iterations_unit: str = "iterations") -> None:
        self.notified_jobs.append({'job': job})


def wait_for_true(func, timeout=FUTURE_TIMEOUT):
    slept = 0
    time_to_sleep = 0.1
    while not func():
        time.sleep(time_to_sleep)
        slept += time_to_sleep
        if slept > timeout:
            raise Exception("Wait timeout for func {func}".format(func=func))

