import asyncio
from unittest.mock import create_autospec
from pathlib import Path
import os
import uuid
import pytest

from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.service import Service
from meeshkan.core.job import Job, JobStatus
from meeshkan.core.tasks import TaskType, Task

from .utils import wait_for_true, MockNotifier

def __get_job(sleep_duration=10):
    return Job.create_job(args=("sleep", str(sleep_duration)), job_number=0, output_path=Path.cwd())

@pytest.fixture
def cleanup():
    # Cleanup for `job`, if possible
    for file in ['stderr', 'stdout']:
        try:
            Path.cwd().joinpath(file).unlink()
        except FileNotFoundError:
            continue



def test_api_submits_job(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job_args = ('echo', 'Hello')
    job = api.submit(job_args)
    scheduler.submit_job.assert_called_with(job)


def test_api_stop_callbacks(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
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


def test_api_as_contextmanager(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)

    with api:
        scheduler.start.assert_called()

    service.stop.assert_called()
    scheduler.stop.assert_called()


@pytest.mark.asyncio
async def test_stopping_job_with_task(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = Scheduler(QueueProcessor())
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job = __get_job()
    with scheduler:  # calls .start() and .stop()
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.RUNNING)
        # Schedule stop job task
        loop = asyncio.get_event_loop()
        loop.create_task(api.handle_task(Task(job.id, TaskType.StopJobTask)))
        wait_for_true(scheduler._job_queue.empty)

    assert job.status in [JobStatus.CANCELLED_BY_USER, JobStatus.CANCELED]


def test_get_notification_status_empty(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = Scheduler(QueueProcessor())
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    assert api.get_notification_status(job.id) == ""


def test_notification_history_no_notifier(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = Scheduler(QueueProcessor())
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    notification_history = api.get_notification_history(job.id)
    assert dict() == notification_history  # Verify for empty history (no notifier)


def test_notification_history_with_notifier(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    notifier = MockNotifier()
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor(), notifier=notifier)
    api = Api(scheduler, service, notifier=notifier)
    job = __get_job(sleep_duration=1)

    with scheduler:  # calls .start() and .stop()
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    notification_history = api.get_notification_history(job.id)
    assert len(notification_history) == 1  # Only one notifier
    assert len(notification_history[notifier.name]) == 2  # Job start, job end
    assert type(notification_history[notifier.name][0]) == str  # transformed


def test_get_job_output(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    output_path, stderr, stdout = api.get_job_output(job.id)
    assert output_path == job.output_path
    assert stderr == job.stderr
    assert stdout == job.stdout


def test_get_job(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)

    assert api.get_job(job.id) is None  # Not submitted to scheduler yet

    scheduler.submit_job(job)
    assert api.get_job(job.id) == job  # Submitted to scheduler



def test_find_job_id(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    # Test by id:
    assert api.find_job_id(job_id=job.id) == job.id
    assert api.find_job_id(job_id=uuid.uuid4()) is None

    # Test by job number
    assert api.find_job_id(job_number=job.number) == job.id
    assert api.find_job_id(job_number=job.number + 1) is None

    # Test by pattern
    pat = "{pat}*".format(pat=job.name[:2])
    assert api.find_job_id(pattern=pat) == job.id
    assert api.find_job_id(pattern="ohnoes*") is None

    # Test all none
    assert api.find_job_id() is None

    # Test precedence via different valid/invalid combinations
    assert api.find_job_id(job_id=job.id, job_number=job.number, pattern=pat) == job.id
    assert api.find_job_id(job_id=job.id, job_number=job.number, pattern="ohnnoes*") == job.id
    assert api.find_job_id(job_id=job.id, job_number=job.number + 1, pattern=pat) == job.id
    assert api.find_job_id(job_id=job.id, job_number=job.number + 1, pattern="boom?") == job.id
    assert api.find_job_id(job_id=uuid.uuid4(), job_number=job.number, pattern=pat) == job.id
    assert api.find_job_id(job_id=uuid.uuid4(), job_number=job.number, pattern="ohnnoes*") == job.id
    assert api.find_job_id(job_id=uuid.uuid4(), job_number=job.number + 1, pattern=pat) == job.id
    assert api.find_job_id(job_id=uuid.uuid4(), job_number=job.number + 1, pattern="boom!") is None
