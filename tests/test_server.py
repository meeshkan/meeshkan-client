from .context import client
from client.server import Server
from .setup import Api, TEST_TMP_FILE
import Pyro4
import pytest


@pytest.mark.skip(reason="requires running test server with `python -m tests.setup`")
def test_server():
    server = Server(tmp_file_name=TEST_TMP_FILE)
    assert server.is_running
    uri = server.get_uri
    api: Api = Pyro4.Proxy(uri)
    api.reset()
    assert api.counter == 0
    api.add()
    assert api.counter == 1
