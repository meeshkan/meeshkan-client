import multiprocessing as mp
from typing import Callable
import logging

import dill
from distutils.version import StrictVersion

import requests
import Pyro4

import meeshkan
from .utils import get_auth, _build_cloud_client
from .core.api import Api
from .core.service import Service

LOGGER = logging.getLogger(__name__)

Pyro4.config.SERIALIZER = 'dill'
Pyro4.config.SERIALIZERS_ACCEPTED.add('dill')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')

__all__ = ["start_agent"]


def __notify_service_start(config: meeshkan.config.Configuration, credentials: meeshkan.config.Credentials):
    cloud_client = _build_cloud_client(config, credentials)
    cloud_client.notify_service_start()
    cloud_client.close()  # Explicitly clean resources


def __verify_version():
    urllib_logger = logging.getLogger("urllib3")
    urllib_logger.setLevel(logging.WARNING)
    pypi_url = "https://pypi.org/pypi/meeshkan/json"
    try:
        res = requests.get(pypi_url, timeout=2)
    except Exception:  # pylint: disable=broad-except
        return  # If we can't access the server, assume all is good
    urllib_logger.setLevel(logging.DEBUG)
    if res.ok:
        latest_release_string = max(res.json()['releases'].keys())  # Textual "max" (i.e. comparison by ascii values)
        latest_release = StrictVersion(latest_release_string)
        current_version = StrictVersion(meeshkan.__version__)
        if latest_release > current_version:  # Compare versions
            print("A newer version of Meeshkan is available!")
            if latest_release.version[0] > current_version.version[0]:  # More messages on major version change...
                print("\tPlease consider upgrading soon with 'pip install meeshkan --upgrade'")
            print()


def start_agent() -> str:
    """
    Starts the agent.
    :raises UnauthorizedException: If credentials have not been setup.
    """
    __verify_version()
    service = Service()
    if service.is_running():
        print("Service is already running.")
        return service.uri

    config, credentials = get_auth()

    __notify_service_start(config, credentials)
    # build_api_serialized = dill.dumps(__build_api(config, credentials))
    pyro_uri = service.start(mp.get_context("spawn"), build_api_serialized=None)
    print('Service started.')
    return pyro_uri
