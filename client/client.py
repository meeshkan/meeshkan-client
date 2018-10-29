import Pyro4
from .server import Server
from .api import Api
from .logger import setup_logging
import logging


def get_logger():
    return logging.getLogger(__name__)


def main():
    setup_logging()
    server = Server()
    logger = get_logger()

    if not server.is_running:
        raise Exception('Start the server first.')

    uri = server.get_uri

    api: Api = Pyro4.Proxy(uri)

    # TODO Add command-line interface here
    api.submit("echo hello")
    logger.info(api.list_jobs())


if __name__ == '__main__':
    main()
