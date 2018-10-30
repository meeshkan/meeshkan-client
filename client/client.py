import Pyro4
import logging
import sys
from api import Api
from logger import setup_logging
from scheduler import start_scheduler


def get_logger():
    return logging.getLogger(__name__)


def main(args):
    setup_logging()
    logger = get_logger()
    # Required for pickling custom classes like Job
    # default serializer is 'serpent', supporting only literal Python expressions
    # see e.g.:
    #    https://github.com/irmen/Serpent
    #    https://pyro-core.narkive.com/iOV3KTdt/custom-class-serialization-with-serpent
    Pyro4.config.SERIALIZER = 'pickle'
    Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
    Pyro4.config.SERIALIZERS_ACCEPTED.add('json')

    # We get the URI after running the daemon, instantiate a Pyro4 Object, and create the API for it
    api: Api = Api(Pyro4.Proxy(start_scheduler()))   # TODO part of commandline for port/host?

    # TODO Add command-line interface here
    api.submit("echo hello")
    logger.info(api.list_jobs())

    # Terminate process
    if len(args) > 0:
        api.terminate_daemon()


if __name__ == '__main__':
    main(sys.argv[1:])
