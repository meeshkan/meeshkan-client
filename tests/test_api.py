import asyncio
from unittest.mock import create_autospec
from pathlib import Path
import os
import pytest

from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.service import Service
from meeshkan.core.job import Job, JobStatus
from meeshkan.core.tasks import TaskType, Task

from .utils import wait_for_true


def test_api_submits_job():
    scheduler = create_autospec(Scheduler).return_value
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job_args = ('echo', 'Hello')
    job = api.submit(job_args)
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


@pytest.mark.asyncio
async def test_stopping_job_with_task():
    scheduler = Scheduler(QueueProcessor())
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job = Job.create_job(args=("sleep", "10"), job_number=0, output_path=Path.cwd())
    with scheduler:  # calls .start() and .stop()
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.RUNNING)
        # Schedule stop job task
        loop = asyncio.get_event_loop()
        loop.create_task(api.handle_task(Task(job.id, TaskType.StopJobTask)))
        wait_for_true(scheduler._job_queue.empty)

    assert job.status in [JobStatus.CANCELLED_BY_USER, JobStatus.CANCELED]

    # Cleanup for `job`
    Path.cwd().joinpath('stderr').unlink()
    Path.cwd().joinpath('stdout').unlink()
