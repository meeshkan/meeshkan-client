# Ignore mypy tests for this file; Attributes for the `meeshkan` package are defined dynamically in
#     __init__.py, so mypy complains about attributes not existing (even though they're well defined).
#     examples for such errors: "error: Name 'meeshkan.config.Configuration' is not defined",
#                               "error: Module has no attribute "config"

import logging

from typing import Tuple

import meeshkan
from .core.cloud import CloudClient
from .core.service import Service
from .core.api import Api
from .exceptions import AgentNotAvailableException

__all__ = ["save_token"]

LOGGER = logging.getLogger(__name__)


def get_auth() -> Tuple[meeshkan.config.Configuration, meeshkan.config.Credentials]:  # type: ignore
    config, credentials = meeshkan.config.init_config()  # type: ignore
    return config, credentials


def save_token(token: str):
    """
    Save Meeshkan API key to ``~/.meeshkan/credentials``.
    Unlike :func:`meeshkan.init`, does not start or restart the agent.
    Creates also the required directories if they do not exist.

    :param token: Meeshkan API key
    """
    meeshkan.config.ensure_base_dirs(verbose=False)  # type: ignore
    meeshkan.config.Credentials.to_isi(refresh_token=token)  # type: ignore


def _get_api() -> Api:
    try:
        api = Service.api()  # type: Api
    except AgentNotAvailableException:
        print("Start the agent first.")
        raise
    return api


def _build_cloud_client(config: meeshkan.config.Configuration,  # type: ignore
                        credentials: meeshkan.config.Credentials) -> CloudClient:  # type: ignore
    cloud_client = CloudClient(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
    return cloud_client
