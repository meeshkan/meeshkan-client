from http import HTTPStatus
import logging
from typing import Callable, Optional
import requests

import meeshkan.exceptions

LOGGER = logging.getLogger(__name__)


class TokenStore(object):
    """
    Fetches and caches access authentication tokens via `_fetch_token` method.
    Call `.close()` to close the underlying requests Session!
    """
    def __init__(self, cloud_url: str, refresh_token: str,
                 build_session: Callable[[], requests.Session] = requests.Session):
        self._auth_url = "{url}/client/auth".format(url=cloud_url)
        self._refresh_token = refresh_token
        self._session = build_session()
        self._token = None  # type: Optional[meeshkan.Token]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def _payload(self) -> meeshkan.Payload:
        return {'refresh_token': self._refresh_token}

    def _fetch_token(self) -> meeshkan.Token:
        LOGGER.debug("Requesting token with payload %s", self._payload)
        resp = self._session.post(self._auth_url, json=self._payload, timeout=15)

        if resp.status_code == HTTPStatus.OK:
            resp_dict = resp.json()
            return resp_dict['access_token']

        if resp.status_code == HTTPStatus.UNAUTHORIZED:
            raise meeshkan.exceptions.UnauthorizedRequestException()

        LOGGER.error("Failed requesting authentication: status %s, text: %s", resp.status_code, resp.text)
        raise RuntimeError("Failed requesting authentication.")

    def get_token(self, refresh=False) -> meeshkan.Token:

        if refresh or self._token is None:
            LOGGER.info("Retrieving new authentication token")
            self._token = self._fetch_token()
        return self._token

    def close(self):
        LOGGER.debug("Closing TokenSource session.")
        self._session.close()
