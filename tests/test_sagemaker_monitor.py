# pylint:disable=redefined-outer-name,no-self-use
import asyncio
from concurrent.futures import Future
from unittest.mock import create_autospec, MagicMock

import botocore
import pytest

from meeshkan.core.job import Job, JobStatus, SageMakerJob
from meeshkan.core.sagemaker_monitor import SageMakerJobMonitor, SageMakerHelper

from meeshkan import exceptions


@pytest.fixture
def mock_boto():
    return MagicMock()


def raise_client_error():
    raise botocore.exceptions.ClientError


def training_job_description_for_status(status):
    return {
        "TrainingJobStatus": status
    }


class TestSageMakerHelper:

    def test_get_job_status(self, mock_boto):
        mock_boto.describe_training_job.return_value = training_job_description_for_status("InProgress")
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        job_name = "spameggs"
        job_status = sagemaker_helper.get_job_status(job_name=job_name)
        mock_boto.describe_training_job.assert_called_with(TrainingJobName=job_name)
        assert job_status == JobStatus.RUNNING

    def test_get_job_status_only_checks_connection_once(self, mock_boto):
        mock_boto.describe_training_job.return_value = training_job_description_for_status("InProgress")
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        job_name = "spameggs"
        sagemaker_helper.get_job_status(job_name=job_name)
        sagemaker_helper.get_job_status(job_name=job_name)
        mock_boto.list_training_jobs.assert_called_once()

    def test_get_job_status_with_broken_boto_raises_exception(self, mock_boto):
        mock_boto.list_training_jobs.side_effect = raise_client_error
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        job_name = "spameggs"
        with pytest.raises(exceptions.SageMakerNotAvailableException):
            sagemaker_helper.get_job_status(job_name=job_name)


def get_mock_coro(return_value):
    async def mock_coro(*args, **kwargs):
        return return_value
    return MagicMock(wraps=mock_coro)


@pytest.fixture
def mock_sagemaker_helper():
    sagemaker_helper = create_autospec(SageMakerHelper).return_value
    sagemaker_helper.wait_for_job_finish = get_mock_coro(return_value=None)
    return sagemaker_helper


@pytest.fixture
def sagemaker_job_monitor(event_loop, mock_sagemaker_helper):
    return SageMakerJobMonitor(event_loop=event_loop,
                               sagemaker_helper=mock_sagemaker_helper,
                               notify_finish=MagicMock())


class TestSageMakerJobMonitor:

    def test_create_queued_job(self, sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "foobar"
        sagemaker_job_monitor.sagemaker_helper.get_job_status.return_value = JobStatus.QUEUED
        job = sagemaker_job_monitor.create_job(job_name=job_name)
        assert job.name == job_name
        assert job.status == JobStatus.QUEUED

    def test_create_running_job(self, sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "foobar"
        sagemaker_job_monitor.sagemaker_helper.get_job_status.return_value = JobStatus.RUNNING
        job = sagemaker_job_monitor.create_job(job_name=job_name)
        assert job.name == job_name
        assert job.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_start_monitor_for_finished_job(self, sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "foobar"
        sagemaker_job_monitor.sagemaker_helper.get_job_status.return_value = JobStatus.FINISHED
        job = sagemaker_job_monitor.create_job(job_name=job_name, poll_interval=0.5)
        update_polling_task, wait_for_finish_task = sagemaker_job_monitor.start(job)
        await asyncio.wait_for(wait_for_finish_task, timeout=5)  # Should finish
        await asyncio.wait_for(update_polling_task, timeout=5)  # Should finish


def sagemaker_available():
    try:
        SageMakerHelper()._check_connection()
        return True
    except Exception as ex:
        print(ex)
        return False


@pytest.fixture
def real_sagemaker_job_monitor(event_loop):
    return SageMakerJobMonitor(event_loop=event_loop)


@pytest.mark.skipif(not sagemaker_available(), reason="Requires local SageMaker credentials, useful for testing though")
class TestRealSageMaker:

    @pytest.mark.asyncio
    async def test_start_monitoring_for_existing_job(self, real_sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "pytorch-rnn-2019-01-04-11-20-03"  # Job we have run in our AWS account
        job = real_sagemaker_job_monitor.create_job(job_name=job_name)
        task = real_sagemaker_job_monitor.start(job)
        await task
        assert job.status == JobStatus.FINISHED

    def test_start_monitoring_for_non_existing_job(self, real_sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "foobar"
        with pytest.raises(exceptions.JobNotFoundException):
            real_sagemaker_job_monitor.create_job(job_name=job_name)
