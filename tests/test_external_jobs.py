from unittest import mock

import meeshkan
from meeshkan.core.service import Service
from meeshkan.core.api import Api


JOB_NAME = "test-job"


def test_as_blocking_job_calls_function_with_correct_arguments():
    function_called = False

    function_args = (1, )
    function_kwargs = {'a': 2}

    @meeshkan.as_blocking_job(job_name=JOB_NAME, report_interval_secs=60)
    def func(*args, **kwargs):
        nonlocal function_called
        function_called = True

        assert args == function_args
        assert kwargs == function_kwargs

    with mock.patch.object(Service, 'api'):
        func(*function_args, **function_kwargs)

    assert function_called


def test_as_blocking_job_calls_service_api():

    @meeshkan.as_blocking_job(job_name=JOB_NAME, report_interval_secs=60)
    def func():
        pass

    mock_get_api = mock.MagicMock()  # type: Api

    with mock.patch.object(Service, 'api', mock_get_api):
        func()
        assert mock_get_api.call_count == 3,\
            "Expected Service.api to have been called when job created, registered, and unregistered"

        # This is the proxy object seen inside context manager
        proxy = mock_get_api.return_value.__enter__.return_value

        proxy.external_jobs.create_external_job.assert_called_once()
        proxy.external_jobs.register_active_external_job.assert_called_once()
        proxy.external_jobs.unregister_active_external_job.assert_called_once()
