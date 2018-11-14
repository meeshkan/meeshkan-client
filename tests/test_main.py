import re
from unittest import mock
import time
import uuid
import subprocess
import requests

import pytest
from click.testing import CliRunner

from .utils import MockResponse
import meeshkan.__main__ as main
import meeshkan.config
import meeshkan.exceptions
import meeshkan.service

CLI_RUNNER = CliRunner()


def run_cli(args):
    return CLI_RUNNER.invoke(main.cli, args=args, catch_exceptions=True)


def _build_session(post_return_value=None, request_return_value=None):
    session: Any = mock.Mock()
    if post_return_value is not None:
        session.post = mock.MagicMock()
        session.post.return_value = post_return_value
    if request_return_value is not None:
        session.request = mock.MagicMock()
        session.request.return_value = request_return_value
    return session

def _token_store(build_session=None):
    """Returns a TokenStore for unit testing"""
    _auth_url = 'favorite-url-yay.com'
    _client_id = 'meeshkan-id-1'
    _client_secret = 'meeshkan-top-secret'
    _token_response = {'access_token': 'token'}
    if build_session is None:
        return meeshkan.oauth.TokenStore(auth_url=_auth_url, client_id=_client_id, client_secret=_client_secret)
    return meeshkan.oauth.TokenStore(auth_url=_auth_url, client_id=_client_id, client_secret=_client_secret, build_session=build_session)


@pytest.fixture
def pre_post_tests():
    """Pre- and post-test method to explicitly start and stop various instances."""
    def _get_fetch_token():
        """
        :return: Function returning tokens that increment by one for every call
        """
        requests_counter = 0
        def fetch(self):
            nonlocal requests_counter
            requests_counter += 1
            return str(requests_counter)
        return fetch
    # Stuff before tests
    tokenstore_patcher = mock.patch('meeshkan.oauth.TokenStore._fetch_token', _get_fetch_token())  # Augment TokenStore
    tokenstore_patcher.start()
    def stop_service():
        run_cli(args=['stop'])
    yield stop_service()
    stop_service()  # Stuff to run after every test
    tokenstore_patcher.stop()


def test_version_break(pre_post_tests):
    original_version = meeshkan.__version__
    meeshkan.__version__ = '0.0.0'
    with pytest.raises(meeshkan.exceptions.OldVersionException):
        CLI_RUNNER.invoke(meeshkan.__main__.cli, args='start', catch_exceptions=False)
    meeshkan.__version__ = original_version


def test_start_stop(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = meeshkan.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        start_result = run_cli('start')
        assert service.is_running()
        stop_result = run_cli(args=['stop'])
        assert not service.is_running()

    assert start_result.exit_code == 0
    assert stop_result.exit_code == 0

    assert mock_cloud_client.return_value.notify_service_start.call_count == 1


def test_start_with_401_fails(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    service = meeshkan.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
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
    service = meeshkan.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
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

    time.sleep(1)  # Hacky way to give some time for finishing the task

    list_result = run_cli(args='list')

    assert job_uuid in list_result.stdout

    # Check stdout and stderr exist
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stdout').is_file()
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stderr').is_file()


def test_sorry_success(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"logUploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=200))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cc = meeshkan.cloud.CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                                    build_session=lambda: mock_session)
    def mock_cc_builder(*args):
        return cc
    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 0
    assert sorry_result.stdout == "Logs uploaded to server succesfully.\n"


def test_sorry_upload_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"logUploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=205))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cc = meeshkan.cloud.CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                                    build_session=lambda: mock_session)

    def mock_cc_builder(*args):
        return cc

    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1
    assert sorry_result.stdout == "Failed uploading logs to server.\n"


def test_sorry_connection_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"logUploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 404))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cc = meeshkan.cloud.CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                                    build_session=lambda: mock_session)

    def mock_cc_builder(*args):
        return cc

    with mock.patch('meeshkan.__main__.__build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.stdout == "Failed uploading logs to server.\n"
    assert sorry_result.exit_code == 1