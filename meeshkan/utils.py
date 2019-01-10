import sys
import logging

from typing import Tuple

from .core.cloud import CloudClient
from .core.config import ensure_base_dirs, init_config, Configuration, Credentials
from .core.service import Service
from .core.api import Api

__all__ = ["save_token"]

LOGGER = logging.getLogger(__name__)


def get_auth() -> Tuple[Configuration, Credentials]:
    config, credentials = init_config()
    return config, credentials


def save_token(token: str):
    ensure_base_dirs(verbose=False)
    Credentials.to_isi(refresh_token=token)


def _get_api() -> Api:
    service = Service()
    if not service.is_running():
        print("Start the service first.")
        sys.exit(1)
    api = service.api  # type: Api
    return api


def _build_cloud_client(config: Configuration,
                        credentials: Credentials) -> CloudClient:
    cloud_client = CloudClient(cloud_url=config.cloud_url, refresh_token=credentials.refresh_token)
    return cloud_client
