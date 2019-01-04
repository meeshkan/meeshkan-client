import asyncio
from unittest.mock import create_autospec
from pathlib import Path
import uuid
import pytest

from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.service import Service
from meeshkan.core.job import Job, JobStatus
from meeshkan.core.job_monitor import SageMakerJobMonitor
from meeshkan.core.tasks import TaskType, Task
from meeshkan import exceptions

from .utils import wait_for_true, MockNotifier


def __get_job(sleep_duration=10):
    return Job.create_job(args=("sleep", str(sleep_duration)), job_number=0, output_path=Path.cwd())


@pytest.fixture
def cleanup():
    yield None
    # Post-test code
    # Cleanup for `job`, if possible
    for file in ['stderr', 'stdout']:
        try:
            Path.cwd().joinpath(file).unlink()
        except FileNotFoundError:
            pass



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

    assert callback_called, "Callback is expected to be called after calling `stop`"
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
    assert api.get_notification_status(job.id) == "", "Without notifiers, notification status is expected to be \"\""


def test_notification_history_no_notifier(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    scheduler = Scheduler(QueueProcessor())
    service = create_autospec(Service).return_value

    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    notification_history = api.get_notification_history(job.id)
    assert dict() == notification_history, "Without notifiers, notification history is expected to be empty"


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
    assert len(notification_history) == 1, "There is only one notifier (e.g. single key in `history`)"
    assert len(notification_history[notifier.name]) == 2, "There should be two events registered! (job start, job end)"
    assert type(notification_history[notifier.name][0]) == str, "Notification history items are expected to be strings"


def test_get_job_output(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    output_path, stderr, stdout = api.get_job_output(job.id)
    assert output_path == job.output_path, "Expected to return internal job output path"
    assert stderr == job.stderr, "Expected to return internal job stderr path"
    assert stdout == job.stdout, "Expected to return internal job stdout path"


def test_get_job(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)

    assert api.get_job(job.id) is None, "Job has not been submitted to scheduler yet, return value should be `None`"

    scheduler.submit_job(job)
    assert api.get_job(job.id) == job, "Job has been submitted to scheduler, returned value should match submitted job"


def test_find_job_id_by_id(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    assert api.find_job_id(job_id=job.id) == job.id, "Job ID should match real job id"
    assert api.find_job_id(job_id=uuid.uuid4()) is None, "Random UUID should return None as no matching job exists"


def test_find_job_id_by_number(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    assert api.find_job_id(job_number=job.number) == job.id, "Job ID should match real job ID"
    assert api.find_job_id(job_number=job.number + 1) is None, "Invalid job number should return None as no matching " \
                                                               "job exists"


def test_find_job_id_by_pattern(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    pat = "{pat}*".format(pat=job.name[:2])
    assert api.find_job_id(pattern=pat) == job.id, "Job ID should match real job ID"
    assert api.find_job_id(pattern="ohnoes*") is None, "Pattern should not match submitted job name and should return " \
                                                       "`None`"


def test_find_job_no_input(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)
    assert api.find_job_id() is None, "Call without arguments should fail silently by returning `None`"


def test_find_job_id_precedence(cleanup):  # pylint:disable=unused-argument,redefined-outer-name
    assert_msg1 = "`find_job_id` should look for job ID by giving precedence to looking by UUID, then by number, then " \
                  "by pattern; One of the possible 7 combinations failed this precedence test."
    assert_msg2 = "`find_job_id` should return `None` as none of the possible arguments matched against submitted job"
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    api = Api(scheduler, service)
    job = __get_job(sleep_duration=1)
    with scheduler:
        scheduler.submit_job(job)
        wait_for_true(lambda: job.status == JobStatus.FINISHED)

    pat = "{pat}*".format(pat=job.name[:2])

    # Test precedence via different valid/invalid combinations
    assert api.find_job_id(job_id=job.id, job_number=job.number, pattern=pat) == \
           api.find_job_id(job_id=job.id, job_number=job.number, pattern="ohnnoes*") == \
           api.find_job_id(job_id=job.id, job_number=job.number + 1, pattern=pat) == \
           api.find_job_id(job_id=job.id, job_number=job.number + 1, pattern="boom?") ==\
           api.find_job_id(job_id=uuid.uuid4(), job_number=job.number, pattern=pat) == \
           api.find_job_id(job_id=uuid.uuid4(), job_number=job.number, pattern="ohnnoes*") == \
           api.find_job_id(job_id=uuid.uuid4(), job_number=job.number + 1, pattern=pat) == job.id, assert_msg1
    assert api.find_job_id(job_id=uuid.uuid4(), job_number=job.number + 1, pattern="boom!") is None, assert_msg2


@pytest.fixture
def mock_api():
    service = create_autospec(Service).return_value
    scheduler = Scheduler(QueueProcessor())
    sagemaker_job_monitor = SageMakerJobMonitor()
    yield Api(scheduler=scheduler,
              service=service,
              sagemaker_job_monitor=sagemaker_job_monitor)
    return None

@pytest.fixture
def mock_aws_access_key():
    import os
    AWS_ACCESS_KEY_ID_NAME = "AWS_ACCESS_KEY_ID"
    AWS_SECRET_ACCESS_KEY = "AWS_SECRET_ACCESS_KEY"
    access_key_id = os.environ.get(AWS_ACCESS_KEY_ID_NAME, "")
    secret_access_key = os.environ.get(AWS_SECRET_ACCESS_KEY, "")
    os.environ[AWS_ACCESS_KEY_ID_NAME] = "foo"
    os.environ[AWS_SECRET_ACCESS_KEY] = "bar"
    yield "foobar"
    # Restore the original
    os.environ[AWS_ACCESS_KEY_ID_NAME] = access_key_id
    os.environ[AWS_SECRET_ACCESS_KEY] = secret_access_key
    return


class TestSagemakerApi:
    def test_start_monitoring_for_existing_job(self, mock_api: Api):
        job_name = "pytorch-rnn-2019-01-04-11-20-03"
        mock_api.monitor_sagemaker(job_name=job_name)

    def test_start_monitoring_for_non_existing_job(self, mock_api: Api):
        job_name = "foobar"
        with pytest.raises(exceptions.JobNotFoundException):
            mock_api.monitor_sagemaker(job_name=job_name)

    def test_sagemaker_not_available(self, mock_api: Api, mock_aws_access_key):
        job_name = "foobar"
        import os
        with pytest.raises(exceptions.SageMakerNotAvailableException):
            print("AWS ACCESS KEY ID", os.environ["AWS_ACCESS_KEY_ID"])
            mock_api.monitor_sagemaker(job_name=job_name)
