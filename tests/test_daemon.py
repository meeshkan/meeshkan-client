import multiprocessing as mp
from unittest.mock import create_autospec

import pytest
from meeshkan.core.service import Service
from meeshkan.core.serializer import DillSerializer
from .utils import PicklableMock

MP_CTX = mp.get_context("spawn")
SERIALIZER = DillSerializer()


@pytest.fixture
def mock_cloud_client():
    return PicklableMock()


def stop_if_running(service_):
    if service_.is_running():
        with service_.api as api:
            api.stop()


@pytest.fixture
def service():
    service_ = Service()
    stop_if_running(service_)
    yield service_
    stop_if_running(service_)


def test_start_stop(service, mock_cloud_client):  # pylint:disable=redefined-outer-name
    service.start(MP_CTX, SERIALIZER(mock_cloud_client))
    assert service.is_running()
    stop_if_running(service_=service)
    assert not service.is_running()


def test_double_start(service, mock_cloud_client):  # pylint:disable=redefined-outer-name
    service.start(MP_CTX, SERIALIZER(mock_cloud_client))
    assert service.is_running()
    with pytest.raises(RuntimeError):
        service.start(MP_CTX, SERIALIZER(mock_cloud_client))
    stop_if_running(service_=service)
    assert not service.is_running()
