import multiprocessing as mp
from unittest.mock import create_autospec

import dill
import pytest
from meeshkan.core.service import Service
from meeshkan.core.api import Api
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.tasks import TaskPoller


def _build_api(service: Service):
    task_poller = create_autospec(TaskPoller).return_value
    return Api(scheduler=Scheduler(QueueProcessor(), task_poller=task_poller), service=service)


def test_start_stop():
    service = Service(mp.get_context("spawn"))
    service.start(dill.dumps(_build_api))
    assert service.stop()


def test_double_start():
    service = Service(mp.get_context("spawn"))
    service.start(dill.dumps(_build_api))
    with pytest.raises(RuntimeError):
        service.start(_build_api)
    service.stop()
