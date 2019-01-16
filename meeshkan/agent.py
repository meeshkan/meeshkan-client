from distutils.version import StrictVersion
import multiprocessing as mp
import logging
from typing import Optional

import dill
import requests
import Pyro4

from . import __utils__
from .core.config import init_config, ensure_base_dirs
from .core.service import Service
from .__version__ import __version__

LOGGER = logging.getLogger(__name__)

Pyro4.config.SERIALIZER = 'dill'
Pyro4.config.SERIALIZERS_ACCEPTED.add('dill')
Pyro4.config.SERIALIZERS_ACCEPTED.add('json')

__all__ = ["start", "init", "stop", "restart"]


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
        current_version = StrictVersion(__version__)
        if latest_release > current_version:  # Compare versions
            print("A newer version of Meeshkan is available!")
            if latest_release.version[0] > current_version.version[0]:  # More messages on major version change...
                print("\tPlease consider upgrading soon with 'pip install meeshkan --upgrade'")
            print()


def init(token: Optional[str] = None):
    """Initialize the Meeshkan agent, optionally with the provided credentials.

    :param token: Meeshkan service token. Only required if credentials have not been setup before.
    """
    ensure_base_dirs()
    try:
        _, credentials = __utils__.get_auth()
    except FileNotFoundError:
        # Credentials not found
        credentials = None

    # Only save supplied token if it's not the same as that included already
    if token and (not credentials or credentials.refresh_token != token):
        print("Stored credentials.")
        __utils__.save_token(token)
        init_config(force_refresh=True)

    restart()


def _stop_if_running() -> bool:
    if Service().is_running():
        print("Stopping service...")
        api = __utils__._get_api()  # pylint: disable=protected-access
        api.stop()
        return True
    return False


def stop():
    """Stop the agent.
    """
    was_running = _stop_if_running()
    if was_running:
        print("Service stopped.")
    else:
        print("Service already stopped.")


def restart():
    """Restart the agent.
    """
    _stop_if_running()
    init_config(force_refresh=True)
    start()


def start() -> str:
    """Start the agent.

    :return str: Pyro server URI.
    """
    __verify_version()
    service = Service()
    if service.is_running():
        print("Service is already running.")
        return service.uri

    config, credentials = __utils__.get_auth()

    cloud_client = __utils__._build_cloud_client(config, credentials)  # pylint: disable=protected-access
    cloud_client.notify_service_start()
    cloud_client_serialized = dill.dumps(cloud_client, recurse=True).decode('cp437')
    pyro_uri = service.start(mp.get_context("spawn"), cloud_client_serialized=cloud_client_serialized)
    print('Service started.')
    cloud_client.close()
    return pyro_uri
