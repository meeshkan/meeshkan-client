import pytest
from meeshkan.service import Service
from meeshkan.api import Api
from meeshkan.scheduler import Scheduler, QueueProcessor


def _build_api(service: Service):
    return Api(scheduler=Scheduler(QueueProcessor()), service=service)


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
