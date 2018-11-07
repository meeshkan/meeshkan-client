from unittest import mock
import time

import pytest
from click.testing import CliRunner

import client.__main__ as main
import client.config
import client.exceptions
import client.service

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


def test_start_stop(stop):  # pylint: disable=unused-argument,redefined-outer-name
    service = client.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('client.__main__.CloudClient', autospec=True) as mock_cloud_client:
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
    service = client.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('client.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Raise Unauthorized exception when service start notified
        def side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            raise client.exceptions.Unauthorized()
        mock_cloud_client.return_value.notify_service_start.side_effect = side_effect
        start_result = run_cli('start')

    assert start_result.exit_code == 1
    assert start_result.stdout == "Unauthorized. Check your credentials.\n"
    assert not service.is_running()
    assert mock_cloud_client.return_value.notify_service_start.call_count == 1


def test_start_submit(stop):  # pylint: disable=unused-argument,redefined-outer-name
    service = client.service.Service()

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch('client.__main__.CloudClient', autospec=True) as mock_cloud_client:
        # Mock notify service start, enough for start-up
        mock_cloud_client.return_value.notify_service_start.return_value = None
        mock_cloud_client.return_value.post_payload.return_value = None
        start_result = run_cli(args=['start'])

    assert start_result.exit_code == 0
    assert service.is_running()

    submit_result = run_cli(args='submit echo Hello')
    assert submit_result.exit_code == 0
    assert "successfully" in submit_result.stdout
    assert service.is_running()

    list_result = run_cli(args='list')
    assert list_result.stdout.endswith("QUEUED']\n")  # Do testing better at some point

    time.sleep(1)  # Hacky way to give some time for finishing the task

    list_result = run_cli(args='list')
    assert list_result.stdout.endswith("FINISHED']\n")
