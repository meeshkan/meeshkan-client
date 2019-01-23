# pylint:disable=redefined-outer-name, no-self-use
import asyncio
from unittest.mock import create_autospec, MagicMock, patch
from pathlib import Path
import uuid
import os
import pytest

from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.service import Service
from meeshkan.core.job import Job, JobStatus, SageMakerJob, ExternalJob
from meeshkan.core.sagemaker_monitor import SageMakerJobMonitor
from meeshkan.core.tasks import TaskType, Task
from meeshkan.api.utils import _notebook_authenticated_session_or_none as nb_authenticate, submit_notebook, \
    _get_notebook_path_generic

from meeshkan.notifications.notifiers import Notifier
from meeshkan import config

from .utils import wait_for_true, MockNotifier, NBServer, MockResponse


def __get_job(sleep_duration=10):
    return Job.create_job(args=("sleep", str(sleep_duration)), job_number=0, output_path=Path.cwd())


@pytest.fixture
def cleanup():
    config.ensure_base_dirs()  # Make sure all the base directories exist before tests
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
def mock_sagemaker_job_monitor():
    return create_autospec(SageMakerJobMonitor).return_value


@pytest.fixture
def mock_api(mock_sagemaker_job_monitor):
    notifier = create_autospec(Notifier).return_value
    mock_event_loop = create_autospec(asyncio.AbstractEventLoop).return_value
    scheduler = Scheduler(QueueProcessor(), notifier=notifier, event_loop=mock_event_loop)
    service = create_autospec(Service).return_value

    yield Api(scheduler=scheduler,
              service=service,
              notifier=notifier,
              sagemaker_job_monitor=mock_sagemaker_job_monitor)


def test_starts_monitoring_queued_sagemaker_job(mock_api: Api):  # pylint:disable=redefined-outer-name
    job_name = "pytorch-rnn-2019-01-04-11-20-03"
    mock_api.sagemaker_job_monitor.create_job.return_value = SageMakerJob(job_name=job_name,
                                                                          status=JobStatus.QUEUED,
                                                                          poll_interval=60)

    job = mock_api.monitor_sagemaker(job_name=job_name)
    mock_api.sagemaker_job_monitor.create_job.assert_called_with(job_name=job_name, poll_interval=None)
    mock_api.sagemaker_job_monitor.start.assert_called_with(job=job)


def test_does_not_start_monitoring_finished_sagemaker_job(mock_api: Api):  # pylint:disable=redefined-outer-name
    job_name = "pytorch-rnn-2019-01-04-11-20-03"
    mock_api.sagemaker_job_monitor.create_job.return_value = SageMakerJob(job_name=job_name,
                                                                          status=JobStatus.FINISHED,
                                                                          poll_interval=60)

    mock_api.monitor_sagemaker(job_name=job_name)
    mock_api.sagemaker_job_monitor.create_job.assert_called_with(job_name=job_name, poll_interval=None)
    mock_api.sagemaker_job_monitor.start.assert_not_called()


class TestExternalJobs:
    JOB_NAME = "test-job"

    def test_create_job_stores_job(self, mock_api: Api):
        job_id = mock_api.external_jobs.create_external_job(pid=0,
                                                            name=TestExternalJobs.JOB_NAME,
                                                            poll_interval=10)
        job = mock_api.scheduler.get_job_by_id(job_id)
        assert job.name == TestExternalJobs.JOB_NAME
        assert job.pid == 0
        assert isinstance(job, ExternalJob)

    def test_register_active_job_notifies_start_and_end(self, mock_api: Api):
        job_id = mock_api.external_jobs.create_external_job(pid=0,
                                                            name=TestExternalJobs.JOB_NAME,
                                                            poll_interval=10)
        job = mock_api.scheduler.get_job_by_id(job_id)
        mock_api.external_jobs.register_active_external_job(job_id=job_id)
        # TODO Wrong level of abstraction tested here as need to access
        # the internals of Scheduler, clean this up
        mock_api.scheduler._notifier.notify_job_start.assert_called_with(job)

        # Smoke test checking that some task was created
        mock_api.scheduler._event_loop.create_task.assert_called_once()

        mock_api.external_jobs.unregister_active_external_job(job_id=job_id)
        mock_api.scheduler._notifier.notify_job_end.assert_called_with(job)


class TestConnectionToNotebookServer:
    NB_PORT = 6666  # non 8888 port so we don't have to close running notebooks locally for tests :innocent:
    NB_IP = "localhost"
    NB_URL = "http://{ip}:{port}/".format(ip=NB_IP, port=NB_PORT)
    NB_KEY = 'abcd'  # Used as token and/or password

    def test_without_token_without_password(self):
        with NBServer(ip=self.NB_IP, port=self.NB_PORT) as nb:
            sess = None
            try:
                sess = nb_authenticate(base_url=nb.url, port=nb.port)
                assert sess is not None, "Unprotected jupyter server should be accessible without a password" \
                                         " (expected a Session object)"
                sess.close()

                sess = nb_authenticate(base_url=nb.url, port=nb.port, notebook_password='bogus')
                assert sess is not None, "Unprotected jupyter server should be accessible regardless if password was " \
                                         "given (expected a Session object)"
                sess.close()
            finally:
                if sess is not None:
                    sess.close()


    def test_with_token_without_password(self):
        with NBServer(ip=self.NB_IP, port=self.NB_PORT, key=self.NB_KEY) as nb:
            sess = None
            try:
                sess = nb_authenticate(base_url=nb.url, port=nb.port)
                assert sess is not None, "Token-protected jupyter server should be accessible without a password" \
                                         " (expected a Session object)"
                sess.close()

                sess = nb_authenticate(base_url=nb.url, port=nb.port, notebook_password='bogus')
                assert sess is not None, "Token-protected jupyter server should be accessible regardless if password " \
                                         "was given (expected a Session object)"
                sess.close()
            finally:
                if sess is not None:
                    sess.close()

    def test_without_token_with_password(self):
        with NBServer(ip=self.NB_IP, port=self.NB_PORT, key=self.NB_KEY, use_password=True) as nb:
            sess = None
            try:
                sess = nb_authenticate(base_url=nb.url, port=nb.port)
                assert sess is None, "Password-protected jupyter server should not be accessible without a password " \
                                     "(expected a None response)"

                sess = nb_authenticate(base_url=nb.url, port=nb.port, notebook_password=self.NB_KEY)
                assert sess is not None, "Password-protected jupyter server should be accessible with the correct " \
                                         "password (expected a Session object)"
                sess.close()

                sess = nb_authenticate(base_url=nb.url, port=nb.port, notebook_password='bogus')
                assert sess is None, "Password-protected jupyter server should not be accessible with the wrong " \
                                     "password (expected a None response)"
            finally:
                if sess is not None:
                    sess.close()


class TestNotebookPathDiscovery:
    KERNEL_ID = "1234-5768-90ab-cdef"
    KERNEL_FILE = os.path.join(os.path.split(__file__)[0], "resources/kernel-1234-5768-90ab-cdef.json")

    def get_valid_shell(self):
        ipython = MagicMock()
        ipython.__class__.__name__ = 'ZMQInteractiveShell'
        return ipython

    def get_kernel_file(self):
        return TestNotebookPathDiscovery.KERNEL_FILE

    def test_from_non_ipython(self):
        with pytest.raises(RuntimeError):
            _get_notebook_path_generic(get_ipython_function=None, list_servers_function=lambda: list(),
                                       connection_file_function=self.get_kernel_file)

    def test_from_non_notebook_ipython(self):
        ipython = MagicMock()
        with pytest.raises(ValueError):
            _get_notebook_path_generic(get_ipython_function=lambda: ipython, list_servers_function=lambda: list(),
                                       connection_file_function=lambda: "")

    def test_from_notebook_ipython_no_connection_file(self):
        with pytest.raises(RuntimeError):
            _get_notebook_path_generic(get_ipython_function=self.get_valid_shell, list_servers_function=lambda: list(),
                                       connection_file_function=lambda: "")

    def test_from_notebook_ipython(self):
        token = None
        valid_kernel = True
        fake_path = 'eggs'
        notebook_dir = 'spam'

        def fake_get(_, *args, **kwargs):  # Used to override the Session.get in _get_notebook_path_generic
            nonlocal valid_kernel, token
            url = args[0]

            if "login" in url:  # login URL and access is tested in TestConnectionToNotebookServer
                return MockResponse()  # Return a passing response

            if token is not None:  # If token-based access, verify the correct token was in use
                assert "token={token}".format(token=token) in url

            if "api/sessions" in url:  # Return matching data to describe notebook instances
                if valid_kernel:
                    return MockResponse(json_data=[{'kernel': {'id': self.KERNEL_ID}, 'notebook': {'path': fake_path}}])
                return MockResponse(json_data=[{'kernel': {'id': 'boom'}}])

        def fake_server():  # Returns a list of running "servers"
            nonlocal token
            return [{'url': 'foo', 'port': 1337, 'token': token, 'notebook_dir': notebook_dir}]

        with patch("requests.Session.get", fake_get):
            path = _get_notebook_path_generic(get_ipython_function=self.get_valid_shell,
                                              list_servers_function=fake_server,
                                              connection_file_function=self.get_kernel_file)
            assert path is not None, "Valid access to notebook server and files, expecting correct path response"
            assert path == "{nbdir}/{nbname}".format(nbdir=notebook_dir, nbname=fake_path)

            token = "zot"
            path = _get_notebook_path_generic(get_ipython_function=self.get_valid_shell,
                                              list_servers_function=fake_server,
                                              connection_file_function=self.get_kernel_file)
            assert path is not None, "Valid token-based access to notebook server and files, expecting correct path" \
                                     " response"
            assert path == "{nbdir}/{nbname}".format(nbdir=notebook_dir, nbname=fake_path)

            valid_kernel = False
            path = _get_notebook_path_generic(get_ipython_function=self.get_valid_shell,
                                              list_servers_function=fake_server,
                                              connection_file_function=self.get_kernel_file)
            assert path is None, "No valid kernel found, expecting a None response"
