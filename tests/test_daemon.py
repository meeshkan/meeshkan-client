import pytest
from meeshkan.exceptions import AgentNotAvailableException
from meeshkan.core.service import Service
from meeshkan.core.serializer import Serializer
from .utils import PicklableMock

@pytest.fixture
def mock_cloud_client():
    return PicklableMock()


def stop_if_running():
    if Service.is_running():
        with Service.api() as api:
            api.stop()


@pytest.fixture
def start_stop_agent():
    stop_if_running()
    assert not Service.is_running()
    yield
    stop_if_running()
    assert not Service.is_running()


def test_start_stop(start_stop_agent, mock_cloud_client):  # pylint:disable=redefined-outer-name
    Service.start(Serializer.serialize(mock_cloud_client))
    assert Service.is_running()


def test_double_start(start_stop_agent, mock_cloud_client):  # pylint:disable=redefined-outer-name
    Service.start(Serializer.serialize(mock_cloud_client))
    assert Service.is_running()
    with pytest.raises(RuntimeError):
        Service.start(Serializer.serialize(mock_cloud_client))


def test_getting_api_before_start_raises_exception():  # pylint:disable=redefined-outer-name
    assert not Service.is_running()
    with pytest.raises(AgentNotAvailableException):
        Service.api()
