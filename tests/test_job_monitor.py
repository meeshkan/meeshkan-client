import asyncio
from unittest.mock import create_autospec, MagicMock
import pytest

import botocore

from meeshkan.core.job import Job, JobStatus, SageMakerJob
from meeshkan.core.job_monitor import SageMakerJobMonitor, SageMakerHelper


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

    def test_build_with_failing_job_list(self, mock_boto):  # pylint:disable=redefined-outer-name
        # mock_boto.list_training_jobs = MagicMock()
        mock_boto.list_training_jobs.side_effect = raise_client_error
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        assert not sagemaker_helper.enabled, "Expected SageMakerHelper to not be enabled if client call raises Error"

    def test_build_with_succeeding_job_list(self, mock_boto):
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        assert sagemaker_helper.enabled, "Expected SageMakerHelper to be enabled if client works without errors"

    def test_get_job_status(self, mock_boto):
        mock_boto.describe_training_job.return_value = training_job_description_for_status("InProgress")
        sagemaker_helper = SageMakerHelper(client=mock_boto)
        job_name = "spameggs"
        job_status = sagemaker_helper.get_job_status(job_name=job_name)
        mock_boto.describe_training_job.assert_called_with(TrainingJobName=job_name)
        assert job_status == JobStatus.RUNNING


class TestSageMakerJobMonitor:

    def test_start(self):
        pass

"""
def sagemaker_available():
    try:
        SageMakerHelper().check_sagemaker_connection()
        return True
    except exceptions.SageMakerNotAvailableException:
        return False


@pytest.mark.skipif(not sagemaker_available(), reason="Requires local SageMaker credentials, useful for testing though")
class TestSagemakerApi:
    def test_start_monitoring_for_existing_job(self, mock_api: Api):
        job_name = "pytorch-rnn-2019-01-04-11-20-03"
        mock_api.sagemaker_job_monitor.assert_called()
        mock_api.monitor_sagemaker(job_name=job_name)

    def test_start_monitoring_for_non_existing_job(self, mock_api: Api):
        job_name = "foobar"
        with pytest.raises(exceptions.JobNotFoundException):
            mock_api.monitor_sagemaker(job_name=job_name)

    def test_sagemaker_not_available(self, mock_api: Api, mock_aws_access_key):
        job_name = "foobar"
        import os
        with pytest.raises(exceptions.SageMakerNotAvailableException):
            print("AWS ACCESS KEY ID", os.environ["AWS_ACCESS_KEY_ID"])
            mock_api.monitor_sagemaker(job_name=job_name)
"""