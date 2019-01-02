from http import HTTPStatus
import logging
from typing import Callable, Optional, List
import requests

from ..exceptions import UnauthorizedRequestException
from ..__types__ import Token, Payload

LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class TokenStore(object):
    """
    Fetches and caches access authentication tokens via `_fetch_token` method.
    Call `.close()` to close the underlying requests Session!
    """
    def __init__(self, refresh_token: str):
        self._token = None  # type: Optional[Token]
        self._refresh_token = refresh_token

    def _fetch_token(self) -> Token:
        raise NotImplementedError

    def get_token(self, refresh=False) -> Token:
        if refresh or self._token is None:
            LOGGER.info("Retrieving new authentication token")
            self._token = self._fetch_token()
        return self._token
