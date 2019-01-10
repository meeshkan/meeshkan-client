# type: ignore
# Ignore mypy tests for this file; Attributes for the `meeshkan` package are defined dynamically in
#     __init__.py, so mypy complains about attributes not existing (even though they're well defined).
#     examples for such errors: "error: Name 'meeshkan.Service' is not defined",
#                               "error: Module has no attribute "Service"

import sys
import logging

from typing import Tuple

import meeshkan
from .core.cloud import CloudClient
from .core.service import Service
from .core.api import Api

__all__ = ["save_token"]

LOGGER = logging.getLogger(__name__)


def get_auth() -> Tuple[meeshkan.config.Configuration, meeshkan.config.Credentials]:
    config, credentials = meeshkan.config.init_config()
    return config, credentials


def save_token(token: str):
    meeshkan.config.ensure_base_dirs(verbose=False)
    meeshkan.config.Credentials.to_isi(refresh_token=token)


def _get_api() -> Api:
    service = Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api = service.api  # type: Api
    return api


def _build_cloud_client(config: meeshkan.config.Configuration,
                        credentials: meeshkan.config.Credentials) -> CloudClient:
    cloud_client = CloudClient(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
    return cloud_client
