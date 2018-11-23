from unittest.mock import create_autospec

import pytest
from meeshkan import Service, Api, Scheduler
from meeshkan.core.scheduler import QueueProcessor
from meeshkan.core.tasks import TaskPoller


def _build_api(service: Service):
    task_poller = create_autospec(TaskPoller).return_value
    return Api(scheduler=Scheduler(QueueProcessor(), task_poller=task_poller), service=service)


def test_start_stop():
    service = Service()
    service.start(_build_api)
    assert service.stop()


def test_double_start():
    service = Service()
    service.start(_build_api)
    with pytest.raises(RuntimeError):
        service.start(_build_api)
    service.stop()
