import pytest
from client.service import Service
from client.api import Api
from client.scheduler import Scheduler


def _build_api(service: Service):
    return Api(scheduler=Scheduler(), service=service)


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
