from unittest.mock import create_autospec

from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler
from meeshkan.core.service import Service


def test_api_submits_job():
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job_args = ('echo', 'Hello')
    job = api.submit(job_args)
    scheduler.create_job.assert_called_with(job_args, name=None, poll_interval=None)
    scheduler.submit_job.assert_called_with(job)


def test_api_stop_callbacks():
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)

    callback_called = False

    def callback():
        nonlocal callback_called
        callback_called = True

    api.add_stop_callback(callback)

    api.stop()

    assert callback_called
    service.stop.assert_called()
    scheduler.stop.assert_called()


def test_api_as_contextmanager():
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)

    with api:
        scheduler.start.assert_called()

    service.stop.assert_called()
    scheduler.stop.assert_called()