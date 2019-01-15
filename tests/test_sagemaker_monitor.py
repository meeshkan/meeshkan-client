# pylint:disable=redefined-outer-name,no-self-use
import asyncio
from unittest.mock import create_autospec, MagicMock

import pandas as pd
import pytest
import sagemaker

from meeshkan.core.job import SageMakerJob, JobStatus
from meeshkan.core.sagemaker_monitor import SageMakerJobMonitor, SageMakerHelper, ScalarHelper

from meeshkan import exceptions


@pytest.fixture
def mock_boto():
    return MagicMock()


@pytest.fixture
def mock_sagemaker_session():
    return MagicMock()


def raise_client_error():
    raise RuntimeError("Boto client is broken here!")


def training_job_description_for_status(status):
    return {
        "TrainingJobStatus": status
    }


class TestSageMakerHelper:

    def test_get_job_status(self, mock_boto, mock_sagemaker_session):
        mock_boto.describe_training_job.return_value = training_job_description_for_status("InProgress")
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"
        job_status = sagemaker_helper.get_job_status(job_name=job_name)
        mock_boto.describe_training_job.assert_called_with(TrainingJobName=job_name)
        assert job_status == JobStatus.RUNNING

    def test_get_job_status_only_checks_connection_once(self, mock_boto, mock_sagemaker_session):
        mock_boto.describe_training_job.return_value = training_job_description_for_status("InProgress")
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"
        sagemaker_helper.get_job_status(job_name=job_name)
        sagemaker_helper.get_job_status(job_name=job_name)
        mock_boto.list_training_jobs.assert_called_once()

    def test_get_job_status_with_broken_boto_raises_exception(self, mock_boto, mock_sagemaker_session):
        mock_boto.list_training_jobs.side_effect = raise_client_error
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"
        with pytest.raises(exceptions.SageMakerNotAvailableException):
            sagemaker_helper.get_job_status(job_name=job_name)

    def test_wait_for_job_finish_calls_waiter_and_returns_status(self, mock_boto, mock_sagemaker_session):
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"

        mock_boto.describe_training_job.return_value = training_job_description_for_status("Completed")

        status = sagemaker_helper.wait_for_job_finish(job_name=job_name)
        mock_boto.get_waiter.assert_called_once()
        mock_waiter = mock_boto.get_waiter.return_value
        _, wait_call_kw_args = mock_waiter.wait.call_args
        assert wait_call_kw_args['TrainingJobName'] == job_name
        assert status == JobStatus.FINISHED

    def test_get_analytics_stores_analytics_object(self, mock_boto, mock_sagemaker_session):
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"

        sagemaker_helper.get_training_job_analytics_df(job_name)
        assert job_name in sagemaker_helper.analytics_by_job_name

    def test_get_analytics_reuses_analytics_object(self, mock_boto, mock_sagemaker_session):
        sagemaker_helper = SageMakerHelper(client=mock_boto, sagemaker_session=mock_sagemaker_session)
        job_name = "spameggs"

        mock_training_analytics = create_autospec(sagemaker.analytics.TrainingJobAnalytics).return_value
        sagemaker_helper.analytics_by_job_name[job_name] = mock_training_analytics
        sagemaker_helper.get_training_job_analytics_df(job_name)
        mock_training_analytics.dataframe.assert_called_once()


def get_mock_coro(return_value):
    async def mock_coro(*args, **kwargs):
        return return_value
    return MagicMock(wraps=mock_coro)


@pytest.fixture
def mock_sagemaker_helper():
    sagemaker_helper = create_autospec(SageMakerHelper).return_value
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
        monitoring_task = sagemaker_job_monitor.start(job)
        await asyncio.wait_for(monitoring_task, timeout=1)  # Should finish
        sagemaker_job_monitor.sagemaker_helper.wait_for_job_finish.assert_called_once()
        sagemaker_job_monitor.notify_finish.assert_called_with(job)

    def test_compute_df_diff_for_no_changes(self):
        df_old = pd.DataFrame.from_dict({'timestamp': [1, 2], 'metric_name': ['epoch', 'loss'], 'value': [1, 3.2]})
        df_new = df_old.copy()
        df_diff = SageMakerJobMonitor.get_new_records(df_new=df_new, df_old=df_old)
        assert len(df_diff) == 0

    def test_compute_df_diff_for_new_row(self):
        df_old = pd.DataFrame.from_dict({'timestamp': [1, 2], 'metric_name': ['epoch', 'loss'], 'value': [1, 3.2]})
        new_row = {'timestamp': 3, 'metric_name': 'loss', 'value': 2.3}
        df_new = df_old.copy().append(new_row, ignore_index=True)
        assert len(df_old) == 2
        assert len(df_new) == 3
        df_diff = SageMakerJobMonitor.get_new_records(df_new=df_new, df_old=df_old)
        assert len(df_diff) == 1
        row = df_diff[0]
        assert row['timestamp'] == new_row['timestamp']
        assert row['metric_name'] == new_row['metric_name']
        assert row['value'] == new_row['value']


@pytest.fixture
def example_sm_record():
    return {'metric_name': 'train_loss', 'value': 2.3, 'timestamp': 0.0}


@pytest.fixture
def sagemaker_job(sagemaker_job_monitor):
    job_name = "spameggs"
    return sagemaker_job_monitor.create_job(job_name=job_name)

@pytest.fixture
def job_scalar_helper():
    sagemaker_job = create_autospec(SageMakerJob).return_value
    return ScalarHelper(job=sagemaker_job)


class TestJobScalarHelper:

    def test_adding_new_metric(self, example_sm_record, job_scalar_helper):
        dataframe = pd.DataFrame.from_dict([example_sm_record])
        sagemaker_job = job_scalar_helper.job
        job_scalar_helper.add_new_scalars_from(dataframe)
        sagemaker_job.add_scalar_to_history.assert_called_once_with(
            scalar_name=example_sm_record['metric_name'],
            scalar_value=example_sm_record['value'])

    def test_adding_same_metric_twice(self, example_sm_record, job_scalar_helper):
        dataframe = pd.DataFrame.from_dict([example_sm_record])
        sagemaker_job = job_scalar_helper.job
        job_scalar_helper.add_new_scalars_from(dataframe)
        job_scalar_helper.add_new_scalars_from(dataframe)
        sagemaker_job.add_scalar_to_history.assert_called_once_with(
            scalar_name=example_sm_record['metric_name'],
            scalar_value=example_sm_record['value'])

    def test_appending_new_record_with_larger_timestamp(self, example_sm_record, job_scalar_helper):
        dataframe = pd.DataFrame.from_dict([example_sm_record])
        sagemaker_job = job_scalar_helper.job

        job_scalar_helper.add_new_scalars_from(dataframe)

        # Create new record
        new_record = example_sm_record.copy()
        new_record.update(timestamp=1.0, value=23.0)
        dataframe_with_two_records = pd.DataFrame.from_dict([example_sm_record, new_record])

        job_scalar_helper.add_new_scalars_from(dataframe_with_two_records)

        assert sagemaker_job.add_scalar_to_history.call_count == 2, "Expected scalar to have been added only twice"

        sagemaker_job.add_scalar_to_history.assert_any_call(
            scalar_name=example_sm_record['metric_name'],
            scalar_value=example_sm_record['value'])

        sagemaker_job.add_scalar_to_history.assert_called_with(
            scalar_name=new_record['metric_name'],
            scalar_value=new_record['value'])


def sagemaker_available():
    try:
        SageMakerHelper().check_or_build_connection()
        return True
    except Exception as ex:
        print(ex)
        return False


@pytest.fixture
def real_sagemaker_job_monitor(event_loop):
    return SageMakerJobMonitor(event_loop=event_loop)


# @pytest.mark.skipif(not sagemaker_available(), reason="Requires local SageMaker credentials, useful for testing though")
@pytest.mark.skip
class TestRealSageMaker:

    @pytest.mark.asyncio
    async def test_start_monitoring_for_existing_job(self, real_sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "pytorch-rnn-2019-01-04-11-20-03"  # Job we have run in our AWS account
        job = real_sagemaker_job_monitor.create_job(job_name=job_name)
        monitoring_task = real_sagemaker_job_monitor.start(job)
        await monitoring_task
        assert job.status == JobStatus.FINISHED

    def test_start_monitoring_for_non_existing_job(self, real_sagemaker_job_monitor: SageMakerJobMonitor):
        job_name = "foobar"
        with pytest.raises(exceptions.JobNotFoundException):
            real_sagemaker_job_monitor.create_job(job_name=job_name)
