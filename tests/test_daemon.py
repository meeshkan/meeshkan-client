import dill
import pytest
from meeshkan.core.service import Service
from .utils import PicklableMock


@pytest.fixture
def mock_cloud_client():
    return PicklableMock()


def stop_if_running():
    if Service.is_running():
        with Service.api() as api:
            api.stop()


def test_start_stop(mock_cloud_client):  # pylint:disable=redefined-outer-name
    Service.start(dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    assert Service.is_running()
    stop_if_running()
    assert not Service.is_running()


def test_double_start(mock_cloud_client):  # pylint:disable=redefined-outer-name
    Service.start(dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    assert Service.is_running()
    with pytest.raises(RuntimeError):
        Service.start(dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    stop_if_running()
    assert not Service.is_running()
