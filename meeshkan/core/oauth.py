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
    def __init__(self, cloud_url: str, refresh_token: str,
                 build_session: Callable[[], requests.Session] = requests.Session):
        self._auth_url = cloud_url
        self._refresh_token = refresh_token
        self._session = build_session()
        self._token = None  # type: Optional[Token]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def _payload(self) -> Payload:
        # TODO do we need to fetch expires_in, scope, id_token and/or token_type?
        query = "query GetToken($refresh_token: String!) { token(refreshToken: $refresh_token) { access_token } }"
        return {"query": query, "variables": {"refresh_token": self._refresh_token}}

    def _fetch_token(self) -> Token:
        LOGGER.debug("Requesting token with payload %s", self._payload)
        resp = self._session.post(self._auth_url, json=self._payload, timeout=15)

        if resp.status_code == HTTPStatus.OK:
            resp_dict = resp.json()['data']
            return resp_dict['token']['access_token']

        if resp.status_code == HTTPStatus.UNAUTHORIZED:
            raise UnauthorizedRequestException()

        LOGGER.error("Failed requesting authentication: status %s, text: %s", resp.status_code, resp.text)
        raise RuntimeError("Failed requesting authentication.")

    def get_token(self, refresh=False) -> Token:

        if refresh or self._token is None:
            LOGGER.info("Retrieving new authentication token")
            self._token = self._fetch_token()
        return self._token

    def close(self):
        LOGGER.debug("Closing TokenSource session.")
        self._session.close()
