import re
from unittest import mock
import time
import uuid
import subprocess
import requests

import pytest
from click.testing import CliRunner

import meeshkan.__main__ as main
import meeshkan.config
import meeshkan.exceptions
import meeshkan.service

CLI_RUNNER = CliRunner()


def run_cli(args):
    return CLI_RUNNER.invoke(main.cli, args=args, catch_exceptions=False)


# Stop service before and after every test
@pytest.fixture
def stop():
    def stop_service():
        run_cli(args=['stop'])
    yield stop_service()
    stop_service()

def test_version_break(stop):
    original_version = meeshkan.__version__
    meeshkan.__version__ = '0.0.0'
    with pytest.raises(meeshkan.exceptions.OldVersionException):
        CLI_RUNNER.invoke(meeshkan.__main__.cli, args='start', catch_exceptions=False)
    meeshkan.__version__ = original_version

def test_start_stop(stop):  # pylint: disable=unused-argument,redefined-outer-name
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


def test_start_with_401_fails(stop):  # pylint: disable=unused-argument,redefined-outer-name
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


def test_start_submit(stop):  # pylint: disable=unused-argument,redefined-outer-name
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


def test_sorry_success(stop):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.__main__.requests', autospec=True) as mock_main_requests,\
            mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
        resp = requests.Response()  # Patch the CloudClient to return a valid answer
        resp.status_code = 200
        resp._content = bytes('{"data": {"logUploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}', 'utf8')
        mock_cloud_client.return_value.post_payload.return_value = resp

        mock_main_requests.get = requests.get  # Patch 'requests.get' to be the actual method (for __verify_version)
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 0
    assert sorry_result.stdout == "Logs uploaded successfully.\n"


def test_sorry_upload_fail(stop):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.__main__.requests', autospec=True) as mock_main_requests,\
            mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
        resp = requests.Response()  # Patch the CloudClient to return a valid answer
        resp.status_code = 200
        resp._content = bytes('{"data": {"logUploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}', 'utf8')
        mock_cloud_client.return_value.post_payload.return_value = resp

        mock_main_requests.get = requests.get  # Patch 'requests.get' to be the actual method (for __verify_version)

        upload_response = requests.Response()
        upload_response.status_code = 405
        def blank(*args, **kwargs):
            return upload_response
        mock_main_requests.request = blank  # Patch 'requests.request' to return a 405 response

        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1
    assert sorry_result.stdout == "Upload to server failed!\n"


def test_sorry_connection_fail(stop):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch('meeshkan.cloud.CloudClient', autospec=True) as mock_cloud_client:
        resp = requests.Response()  # Patch the CloudClient to return a invalid answer
        resp.status_code = 404
        mock_cloud_client.return_value.post_payload.return_value = resp
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1
    assert sorry_result.stdout == "Failed to get upload link from server.\n"