import multiprocessing as mp
import re
from unittest import mock
import time
import uuid
import os

import requests
import pytest
from click.testing import CliRunner

import meeshkan
from meeshkan.core.oauth import TokenStore
from meeshkan.core.cloud import CloudClient
from meeshkan.core.service import Service
import meeshkan.__main__ as main
from .utils import MockResponse

CLI_RUNNER = CliRunner()
MP_CTX = mp.get_context("forkserver")


def run_cli(args):
    return CLI_RUNNER.invoke(main.cli, args=args, catch_exceptions=True)


def _build_session(post_return_value=None, request_return_value=None):
    session = mock.create_autospec(requests.Session)
    if post_return_value is not None:
        session.post.return_value = post_return_value
    if request_return_value is not None:
        session.request.return_value = request_return_value
    return session


def _token_store(build_session=None):
    """Returns a TokenStore for unit testing"""
    _cloud_url = 'favorite-url-yay.com'
    _refresh_token = 'meeshkan-top-secret'
    if build_session is None:
        return TokenStore(cloud_url=_cloud_url, refresh_token=_refresh_token)
    return TokenStore(cloud_url=_cloud_url, refresh_token=_refresh_token, build_session=build_session)


@pytest.fixture
def pre_post_tests():
    """Pre- and post-test method to explicitly start and stop various instances."""
    def _get_fetch_token():
        """
        :return: Function returning tokens that increment by one for every call
        """
        requests_counter = 0

        def fetch(self):  # pylint:disable=unused-argument
            nonlocal requests_counter
            requests_counter += 1
            return str(requests_counter)
        return fetch
    # Stuff before tests
    tokenstore_patcher = mock.patch('meeshkan.__main__.TokenStore._fetch_token', _get_fetch_token())
    tokenstore_patcher.start()  # Augment TokenStore

    def stop_service():
        run_cli(args=['stop'])
    yield stop_service()
    stop_service()  # Stuff to run after every test
    tokenstore_patcher.stop()


def test_version_break(pre_post_tests):  # pylint:disable=unused-argument,redefined-outer-name
    original_version = meeshkan.__version__
    meeshkan.__version__ = '0.0.0'
    with pytest.raises(meeshkan.exceptions.OldVersionException):
        CLI_RUNNER.invoke(meeshkan.__main__.cli, args='start', catch_exceptions=False)
    meeshkan.__version__ = original_version


def test_start_stop(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        start_result = run_cli('start')
        assert service.is_running()
        stop_result = run_cli(args=['stop'])
        assert not service.is_running()

    assert start_result.exit_code == 0
    assert stop_result.exit_code == 0

    assert mock_cloud_client.return_value.notify_service_start.call_count == 1


def test_double_start(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        mock_cloud_client.return_value.notify_service_start.return_value = None
        start_result = run_cli('start')
        assert service.is_running()
        double_start_result = run_cli('start')
        assert double_start_result.stdout == "Service is already running.\n"

    assert start_result.exit_code == 0
    assert double_start_result.exit_code == 1
    assert mock_cloud_client.return_value.notify_service_start.call_count == 1


def test_start_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)

    def fail_notify_start(*args, **kwargs):  # pylint: disable=unused-argument,redefined-outer-name
        raise RuntimeError

    patcher = mock.patch('meeshkan.__main__.__notify_service_start', fail_notify_start)  # Augment TokenStore
    patcher.start()
    start_result =  run_cli('start')

    assert start_result.stdout == "Starting service failed.\n"
    assert start_result.exit_code == 1
    assert not service.is_running()
    patcher.stop()


def test_help(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    help_result = run_cli('help')
    assert help_result.exit_code == 0

    help_result = [x.strip() for x in help_result.stdout.split("\n")]
    commands = ['clear', 'help', 'list', 'sorry', 'start', 'status', 'stop', 'submit']
    assert all([any([output.startswith(command) for output in help_result]) for command in commands])

def test_verify_version_failure(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.__main__.requests', autospec=True) as mock_requests:
        def fail_get(*args, **kwargs):   # pylint: disable=unused-argument,redefined-outer-name
            raise Exception
        mock_requests.get.side_effect = fail_get
        assert main.__verify_version() is None


def test_start_with_401_fails(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Raise Unauthorized exception when service start notified
        def side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            raise meeshkan.exceptions.UnauthorizedRequestException()
        mock_cloud_client.return_value.notify_service_start.side_effect = side_effect
        start_result = run_cli('--silent start')

    assert start_result.exit_code == 1
    assert start_result.stdout == "Unauthorized. Check your credentials.\n"
    assert not service.is_running()
    assert mock_cloud_client.return_value.notify_service_start.call_count == 1


def test_start_submit(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        mock_cloud_client.return_value.post_payload.return_value = None
        start_result = run_cli(args=['start'])

    assert start_result.exit_code == 0
    assert service.is_running()

    submit_result = run_cli(args='submit echo Hello')
    assert submit_result.exit_code == 0

    stdout_pattern = r"Job\s(\d+)\ssubmitted\ssuccessfully\swith\sID\s([\w-]+)"
    match = re.match(stdout_pattern, submit_result.stdout)

    job_number = int(match.group(1))
    assert job_number == 0

    job_uuid = match.group(2)
    assert uuid.UUID(job_uuid)

    assert service.is_running()

    list_result = run_cli(args='list')
    assert list_result.exit_code == 0  # Better testing at some point.

    def verify_finished(out):
        out = out.split("\n")  # Split per line
        line = [x for x in out if job_uuid in x]  # Find the one relevant job_id
        assert len(line) == 1
        return "FINISHED" in line[0]

    list_result = run_cli(args='list')
    while not verify_finished(list_result.stdout):
        time.sleep(0.2)  # Hacky way to give some time for finishing the task
        list_result = run_cli(args='list')

    # Check stdout and stderr exist
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stdout').is_file()
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stderr').is_file()


def test_sorry_success(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=200))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client
    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 0
    assert sorry_result.stdout == "Logs uploaded to server succesfully.\n"


def test_sorry_upload_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=205))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client

    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1
    assert sorry_result.stdout == "Failed uploading logs to server.\n"


def test_sorry_connection_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 404))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client

    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.stdout == "Failed uploading logs to server.\n"
    assert sorry_result.exit_code == 1


def test_empty_list(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = Service(MP_CTX)
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        mock_cloud_client.return_value.post_payload.return_value = None
        run_cli(args=['start'])
        list_result = run_cli(args=['list'])

    assert service.is_running()
    assert list_result.exit_code == 0
    assert list_result.stdout == "No jobs submitted yet.\n"


def test_easter_egg(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    easter_egg = run_cli('im-bored')  # No mocking as we don't care about get requests here?
    assert easter_egg.exit_code == 0
    assert easter_egg.stdout.index(":") > 0  # Separates author:name...


def test_clear(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    def do_nothing(*args, **kwargs):
        return
    patch_rmtree = mock.patch('shutil.rmtree', do_nothing)
    patch_rmtree.start()

    clear_result = run_cli(args=['clear'])

    assert clear_result.exit_code == 0
    assert "Removing jobs directory" in clear_result.stdout
    assert "Removing logs directory" in clear_result.stdout
    assert os.path.isdir(meeshkan.config.JOBS_DIR)
    assert os.path.isdir(meeshkan.config.LOGS_DIR)

    patch_rmtree.stop()


def test_status(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        mock_cloud_client.return_value.post_payload.return_value = None

        not_running_status = run_cli(args=['status'])
        assert not_running_status.exit_code == 0
        assert "configured to run" in not_running_status.stdout

        run_cli(args=['start'])
        running_status = run_cli(args=['status'])
        assert running_status.exit_code == 0
        assert "up and running" in running_status.stdout
        assert "URI for Daemon is" in running_status.stdout