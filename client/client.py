import Pyro4
from .server import Server
from .api import Api


def main():
    server = Server()

    if not server.is_running:
        raise Exception('Start the server first.')

    uri = server.get_uri

    api: Api = Pyro4.Proxy(uri)

    api.submit("echo hello")
    print(api.list_jobs())


if __name__ == '__main__':
    main()
