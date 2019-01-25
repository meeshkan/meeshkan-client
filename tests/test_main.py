import re
from unittest import mock
import time
import uuid
import os

import requests
import pytest
from click.testing import CliRunner

import meeshkan
from meeshkan.core.cloud import CloudClient
from meeshkan.core.service import Service
from meeshkan.exceptions import UnauthorizedRequestException
import meeshkan.__main__ as main
from .utils import MockResponse, DummyStore, PicklableMock

CLI_RUNNER = CliRunner()


BUILD_CLOUD_CLIENT_PATCH_PATH = 'meeshkan.__utils__._build_cloud_client'


def run_cli(args, inputs=None, catch_exceptions=True):
    return CLI_RUNNER.invoke(main.cli, args=args, catch_exceptions=catch_exceptions, input=inputs)


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
        return DummyStore(cloud_url=_cloud_url, refresh_token=_refresh_token)
    return DummyStore(cloud_url=_cloud_url, refresh_token=_refresh_token, build_session=build_session)


@pytest.fixture
def pre_post_tests():
    """Pre- and post-test method to explicitly start and stop various instances."""

    def stop_service():
        run_cli(args=['stop'])
    yield stop_service()
    stop_service()  # Stuff to run after every test


def test_setup_if_exists(pre_post_tests):  # pylint:disable=unused-argument,redefined-outer-name
    """Tests `meeshkan setup` if the credentials file exists
    Does not test wrt to Git access token; that's tested separately in test_config"""
    # Mock credentials writing (tested in test_config.py)
    temp_token = "abc"

    def to_isi(refresh_token, git_access_token, *args):
        assert refresh_token == temp_token, "Refresh token token used is '{}'!".format(temp_token)
        assert git_access_token == "", "No git access token is given!"

    with mock.patch("meeshkan.config.Credentials.to_isi") as mock_to_isi:
        with mock.patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = True
            mock_to_isi.side_effect = to_isi

            # Test with proper interaction
            run_cli(args=['setup'], inputs="y\n{token}\n\n".format(token=temp_token), catch_exceptions=False)
            assert mock_to_isi.call_count == 1, "`to_isi` should only be called once (proper response)"

            # Test with empty response
            run_cli(args=['setup'], inputs="\n{token}\n\n".format(token=temp_token), catch_exceptions=False)
            assert mock_to_isi.call_count == 2, "`to_isi` should be called twice here (default response)"

            # Test with non-positive answer
            config_result = run_cli(args=['setup'], inputs="asdasdas\n{token}\n\n".format(token=temp_token),
                                    catch_exceptions=False)
            assert mock_to_isi.call_count == 2, "`to_isi` should still be called only twice (negative answer)"
            assert config_result.exit_code == 2, "Exit code should be non-zero (2 - cancelled by user)"


def test_setup_if_doesnt_exists(pre_post_tests):  # pylint:disable=unused-argument,redefined-outer-name
    """Tests `meeshkan setup` if the credentials file does not exist
    Does not test wrt to Git access token; that's tested separately in test_config"""
    # Mock credentials writing (tested in test_config.py)
    temp_token = "abc"

    def to_isi(refresh_token, git_token, *args):
        assert refresh_token == temp_token, "Refresh token token used is '{}'!".format(temp_token)
        assert git_token == "", "No git access token is given!"

    with mock.patch("meeshkan.config.Credentials.to_isi") as mock_to_isi:
        with mock.patch("os.path.isfile") as mock_isfile:
            mock_isfile.return_value = False
            mock_to_isi.side_effect = to_isi
            # Test with proper interaction
            run_cli(args=['setup'], inputs="{token}\n\n".format(token=temp_token), catch_exceptions=False)
            assert mock_to_isi.call_count == 1, "`to_isi` should only be called once (token given)"

            # Test with empty response
            temp_token = ''
            run_cli(args=['setup'], inputs="\n\n", catch_exceptions=False)
            assert mock_to_isi.call_count == 2, "`to_isi` should be called twice here (empty token)"


@pytest.mark.skip("This is hard to test at the moment")
def test_version_mismatch_major(pre_post_tests):  # pylint:disable=unused-argument,redefined-outer-name
    original_version = meeshkan.__version__
    meeshkan.__version__ = '0.0.0'
    with mock.patch("requests.get") as mock_requests_get:  # Mock requests.get specifically for version test...
        mock_requests_get.return_value = MockResponse({"releases": {"20.0.0": {}, "2.0.0": {}}}, 200)
        version_result = run_cli(args=['start'], catch_exceptions=False)
        assert "pip install" in version_result.stdout, "New version available! Client should suggest how to update"
        assert "newer version" in version_result.stdout, "New major version available! Client should notify user"
    meeshkan.__version__ = original_version


@pytest.mark.skip("This is hard to test at the moment")
def test_version_mismatch(pre_post_tests):  # pylint:disable=unused-argument,redefined-outer-name
    original_version = meeshkan.__version__
    meeshkan.__version__ = '0.0.0'
    with mock.patch("requests.get") as mock_requests_get:  # Mock requests.get specifically for version test...
        mock_requests_get.return_value = MockResponse({"releases": {"0.1.0": {}, "0.0.1": {}}}, 200)
        version_result = run_cli(args=['start'], catch_exceptions=False)
        assert "pip install" not in version_result.stdout, "New version minor available! Client should be quieter..."
        assert "newer version" in version_result.stdout, "New major version available! Client should notify user"
    meeshkan.__version__ = original_version


def test_start_stop(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    # Patch CloudClient as it connects to cloud at start-up
    # Lots of reverse-engineering happening here...
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        mock_cloud_client.notify_service_start.return_value = None
        start_result = run_cli('start')
        assert start_result.exit_code == 0
        assert Service.is_running(), "Service should be running after using `meeshkan start`"
        stop_result = run_cli(args=['stop'])
        assert not Service.is_running(), "Service should NOT be running after using `meeshkan stop`"

    assert start_result.exit_code == 0, "`meeshkan start` is expected to run without errors"
    assert stop_result.exit_code == 0, "`meeshkan stop` is expected to run without errors"

    assert mock_cloud_client.notify_service_start.call_count == 1, "`notify_service_start` is expected " \
                                                                                "to be called only once."


def test_double_start(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        mock_cloud_client.notify_service_start.return_value = None
        start_result = run_cli('start')
        assert Service.is_running(), "Service should be running after using `meeshkan start`"
        double_start_result = run_cli('start')
        assert double_start_result.stdout == "Service is already running.\n", "Service should already be running"

    assert start_result.exit_code == 0, "`meeshkan start` should succeed by default"
    assert double_start_result.exit_code == 0, "Consecutive calls to `meeshkan start`are allowed"
    assert mock_cloud_client.notify_service_start.call_count == 1, "`notify_service_start` is expected " \
                                                                                "to be called only once"


def test_start_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    def fail_notify_start(*args, **kwargs):  # pylint: disable=unused-argument,redefined-outer-name
        raise RuntimeError("Mocking notify service start failure")

    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        mock_cloud_client.notify_service_start.side_effect = fail_notify_start
        start_result = run_cli('start')

    assert "Starting the Meeshkan agent failed" in start_result.stdout,\
        "`meeshkan start` is expected to fail with error message"
    assert start_result.exit_code == 1, "`meeshkan start` exit code should be non-zero upon failure"
    assert not Service.is_running(), "Service should not be running!"


def test_help(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    assert_msg1 = "All the commands in __main__ should be listed under `meeshkan help`"
    help_result = run_cli('help')
    assert help_result.exit_code == 0, "`meeshkan help` should run without errors!"

    help_result = [x.strip() for x in help_result.stdout.split("\n")]
    commands = ['cancel', 'clean', 'clear', 'help', 'list', 'logs', 'notifications', 'report', 'setup', 'sorry',
                'start', 'status', 'stop', 'submit']
    assert all([any([output.startswith(command) for output in help_result]) for command in commands]), assert_msg1


def test_start_with_401_fails(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name

    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        # Raise Unauthorized exception when service start notified
        def side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            raise meeshkan.exceptions.UnauthorizedRequestException()
        mock_cloud_client.notify_service_start.side_effect = side_effect
        start_result = run_cli('--silent start')

    assert start_result.exit_code == 1, "`meeshkan start` is expected to fail with UnauthorizedRequestException and " \
                                        "return a non-zero exit code"
    assert start_result.stdout == UnauthorizedRequestException().message + '\n', "stdout when running `meeshkan " \
                                                                                 "start` should match the error " \
                                                                                 "message in " \
                                                                                 "UnauthorizedRequestException"
    assert not Service.is_running(), "Service should not be running after a failed `start`"
    assert mock_cloud_client.notify_service_start.call_count == 1, "`notify_service_start` should be " \
                                                                                "called once (where it fails)"


def test_start_submit(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    # Patch CloudClient as it connects to cloud at start-up
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        # Mock notify service start, enough for start-up
        mock_cloud_client.notify_service_start.return_value = None
        mock_cloud_client.post_payload.return_value = None
        start_result = run_cli(args=['start'])

    assert start_result.exit_code == 0, "`start` should run smoothly"
    assert Service.is_running(), "Service should be running after `start`"

    submit_result = run_cli(args='echo Hello')  # if it works without the `submit`, it will work with it
    assert submit_result.exit_code == 0, "`submit` is expected to succeed"

    stdout_pattern = r"Job\s(\d+)\ssubmitted\ssuccessfully\swith\sID\s([\w-]+)"
    match = re.match(stdout_pattern, submit_result.stdout)

    job_number = int(match.group(1))
    assert job_number == 1, "Submitted job should have a HID of 1 (first job submitted)"

    job_uuid = match.group(2)
    assert uuid.UUID(job_uuid), "Job UUID should be a valid UUID and match the regex pattern"

    assert Service.is_running(), "Service should still be running!"

    list_result = run_cli(args='list')
    # Better testing at some point.
    assert list_result.exit_code == 0, "`list` is expected to succeed"

    def verify_finished(out):
        out = out.split("\n")  # Split per line
        line = [x for x in out if job_uuid in x]  # Find the one relevant job_id
        assert len(line) == 1, "There should be only one line with the given job id"
        return "FINISHED" in line[0]

    list_result = run_cli(args='list')
    while not verify_finished(list_result.stdout):
        time.sleep(0.2)  # Hacky way to give some time for finishing the task
        list_result = run_cli(args='list')

    # Check stdout and stderr exist
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stdout').is_file(), "stdout file is expected to exist after " \
                                                                            "job is finished"
    assert meeshkan.config.JOBS_DIR.joinpath(job_uuid, 'stderr').is_file(), "stderr file is expected to exist after " \
                                                                            "job is finished"


def test_sorry_success(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=200))
    mock_token_store = _token_store()  # no need to connect for a token in this instance
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client
    with mock.patch('meeshkan.__main__._build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 0, "`sorry` is expected to succeed"
    assert sorry_result.stdout == "Logs uploaded to server succesfully.\n", "`sorry` output message should match"


def test_sorry_upload_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 200),
                                  request_return_value=MockResponse(status_code=205))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client

    with mock.patch('meeshkan.__main__._build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1, "`sorry` is expected to fail"
    assert sorry_result.stdout == "Failed uploading logs to server.\n", "`sorry` output message should match"


def test_sorry_connection_fail(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    payload = {"data": {"uploadLink": {"upload": "http://localhost", "uploadMethod": "PUT", "headers": ["x:a"]}}}
    mock_session = _build_session(post_return_value=MockResponse(payload, 404))
    mock_token_store = _token_store(build_session=lambda: mock_session)
    cloud_client = CloudClient(cloud_url="http://localhost", token_store=mock_token_store,
                               build_session=lambda: mock_session)

    def mock_cc_builder(*args):  # pylint: disable=unused-argument
        return cloud_client

    with mock.patch('meeshkan.__main__._build_cloud_client', mock_cc_builder):
        sorry_result = run_cli(args=['sorry'])

    assert sorry_result.exit_code == 1, "`sorry` is expected to fail"
    assert sorry_result.stdout == "Failed uploading logs to server.\n", "`sorry` output message should match"


def test_empty_list(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        # Mock notify service start, enough for start-up
        mock_cloud_client.notify_service_start.return_value = None
        mock_cloud_client.post_payload.return_value = None
        run_cli(args=['start'])
        list_result = run_cli(args=['list'])

    assert Service.is_running(), "Service should be running after running `start`"
    assert list_result.exit_code == 0, "`list` is expected to succeed"
    assert list_result.stdout == "No jobs submitted yet.\n", "`list` output message should match"


def test_easter_egg(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    easter_egg = run_cli('im-bored')  # No mocking as we don't care about get requests here?
    assert easter_egg.exit_code == 0, "easter egg is expected to succeed"
    assert easter_egg.stdout.index(":") > 0, "A colon is used in stdout to separate author and content - where is it?"


def test_clear(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    def do_nothing(*args, **kwargs):
        return
    patch_rmtree = mock.patch('shutil.rmtree', do_nothing)
    patch_rmtree.start()

    clear_result = run_cli(args=['clear'])

    assert clear_result.exit_code == 0, "`clear` is expected to succeed"
    assert "Removing jobs directory" in clear_result.stdout, "`clear` output messages should match"
    assert "Removing logs directory" in clear_result.stdout, "`clear` output messages should match"
    # Sanity tests as we're mocking rmtree -> but even if that fails, the directories should be recreated!
    assert os.path.isdir(meeshkan.config.JOBS_DIR), "Default JOBS directory should exist after `clear`"
    assert os.path.isdir(meeshkan.config.LOGS_DIR), "Default LOGS directory should exist after `clear`"

    patch_rmtree.stop()


def test_status(pre_post_tests):  # pylint: disable=unused-argument,redefined-outer-name
    with mock.patch(BUILD_CLOUD_CLIENT_PATCH_PATH) as mock_build_cloud_client:
        mock_cloud_client = PicklableMock()
        mock_build_cloud_client.return_value = mock_cloud_client
        # Mock notify service start, enough for start-up
        mock_cloud_client.notify_service_start.return_value = None
        mock_cloud_client.post_payload.return_value = None

        not_running_status = run_cli(args=['status'])
        assert not_running_status.exit_code == 0, "`status` is expected to succeed even if Service is not running"
        assert "configured to run" in not_running_status.stdout, "`status` message should match"

        run_cli(args=['start'])
        running_status = run_cli(args=['status'])
        assert running_status.exit_code == 0, "`status` is expected to succeed"
        assert "up and running" in running_status.stdout, "`status` message should match"
        assert "URI for Daemon is" in running_status.stdout, "`status` message should match"
