import Pyro4
import os
import tempfile


@Pyro4.expose
class GreetingMaker(object):
    def get_fortune(self, name):
        return "Hello, {0}. Here is your fortune message:\n" \
               "Behold the warranty -- the bold print giveth and the fine print taketh away.".format(name)


class Server(object):

    def __init__(self):
        self._tmp_file = os.path.join(tempfile.gettempdir(), 'pyro_uri.txt')
        self._started_server = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._started_server:  # Wrote the file, free to delete it
            print('Clean-up: deleting', self._tmp_file)
            os.remove(self._tmp_file)

    @property
    def is_running(self):
        return os.path.exists(self._tmp_file)

    @property
    def get_uri(self):
        assert self.is_running is True

        # Check if the file exists
        with open(self._tmp_file, 'r') as f:
            return f.read()

    def register_uri(self, uri):
        os.makedirs(os.path.dirname(self._tmp_file), exist_ok=True)
        with open(self._tmp_file, "w") as f:
            f.write(uri)

    def start(self, cls):
        assert self.is_running is False
        with Pyro4.Daemon(host='127.0.0.1', port=7778) as daemon:  # make a Pyro daemon
            uri = daemon.register(cls)  # register the greeting maker as a Pyro object
            self.register_uri(uri.asString())
            self._started_server = True
            print("URI: {}".format(uri))  # print the uri so we can use it in the client later
            daemon.requestLoop()
        return uri


def main():
    with Server() as server:
        if not server.is_running:
            server.start(GreetingMaker)
        else:
            uri = server.get_uri
            print('Server is already running at {0}'.format(uri))


if __name__ == '__main__':
    main()
