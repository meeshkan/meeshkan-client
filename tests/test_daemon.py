import multiprocessing as mp
from unittest.mock import create_autospec

import dill
import pytest
from meeshkan.core.service import Service
from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.tasks import TaskPoller
from .utils import PicklableMock

MP_CTX = mp.get_context("spawn")


def _build_api(service: Service):
    task_poller = create_autospec(TaskPoller).return_value
    return Api(scheduler=Scheduler(QueueProcessor()), task_poller=task_poller, service=service)


def test_start_stop():
    service = Service()
    mock_cloud_client = PicklableMock()
    service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    assert service.stop(), "Service should be able to stop cleanly after the service is already running!"


def test_double_start():
    service = Service()
    mock_cloud_client = PicklableMock()
    service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    with pytest.raises(RuntimeError):
        service.start(MP_CTX, dill.dumps(mock_cloud_client, recurse=True).decode('cp437'))
    service.stop()
