import pytest
from client.service import Service


def test_start_stop():
    service = Service()
    service.start()
    assert service.stop()

def test_double_start():
    service = Service()
    service.start()
    with pytest.raises(RuntimeError):
        service.start()
    service.stop()