import multiprocessing as mp
from unittest.mock import create_autospec

import dill
import pytest
from meeshkan.core.service import Service
from .utils import PicklableMock

MP_CTX = mp.get_context("spawn")


@pytest.fixture
def mock_cloud_client():
    return PicklableMock()


@pytest.fixture
def service():
    service_ = Service()
    if service_.is_running():
        service_.stop()
    yield service_


def test_start_stop(service, mock_cloud_client):
    service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    assert service.stop(), "Service should be able to stop cleanly after the service is already running!"


def test_double_start(service, mock_cloud_client):
    service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    with pytest.raises(RuntimeError):
        service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    service.stop()
