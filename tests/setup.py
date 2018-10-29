from .context import client
from client.server import Server
import Pyro4

TEST_TMP_FILE = 'pyro_uri_test.txt'


@Pyro4.expose
class Api(object):

    def __init__(self):
        self._counter = 0

    # noinspection PyMethodMayBeStatic
    def add(self):
        self._counter += 1

    @property
    def counter(self):
        return self._counter

    def reset(self):
        self._counter = 0


def start():
    with Server(tmp_file_name=TEST_TMP_FILE) as server:
        server.close(force=True)
        server.start(Api())


if __name__ == '__main__':
    start()
