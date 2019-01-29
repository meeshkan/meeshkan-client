from unittest import mock

import meeshkan

JOB_NAME = "test-job"


def test_as_blocking_job_calls_function_with_correct_arguments():
    function_called = False

    function_args = [1]
    function_kwargs = {'a': 2}

    @meeshkan.as_blocking_job(job_name=JOB_NAME, report_interval_secs=60)
    def func(*args, **kwargs):
        nonlocal function_called
        function_called = True

        assert len(args) == len(function_args)
        assert args[0] == function_args[0]

        assert kwargs == function_kwargs

    with mock.patch('meeshkan.__utils__._get_api'):
        func(*function_args, **function_kwargs)

    assert function_called


def test_as_blocking_job_calls_service_api():

    @meeshkan.as_blocking_job(job_name=JOB_NAME, report_interval_secs=60)
    def func():
        return

    with mock.patch('meeshkan.__utils__._get_api') as mock_get_api:
        func()
        assert mock_get_api.call_count == 3, "Expected Service.api to have been called thrice"
