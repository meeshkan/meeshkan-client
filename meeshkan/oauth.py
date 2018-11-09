from http import HTTPStatus
import logging
from typing import Callable, Dict, NewType

import requests

import meeshkan.exceptions

LOGGER = logging.getLogger(__name__)

Token = NewType("Token", str)
FetchToken = NewType("FetchToken", Callable[[], Token])


class TokenSource(object):
    """
    Fetch access tokens via `fetch` method. Call `.close()` to close the underlying requests Session!
    """
    def __init__(self, auth_url: str, client_id: str, client_secret: str,
                 build_session: Callable[[], requests.Session]):
        self._auth_url = auth_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._session = build_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def _payload(self) -> Dict[str, str]:
        return {
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'audience': "https://api.meeshkan.io",
            "grant_type": "client_credentials"
        }

    def fetch_token(self) -> Token:
        LOGGER.debug("Requesting token with payload %s", self._payload)
        resp = self._session.post("https://{url}/oauth/token".format(url=self._auth_url), data=self._payload, timeout=5)

        if resp.status_code == HTTPStatus.OK:
            resp_dict = resp.json()
            return resp_dict['access_token']

        if resp.status_code == HTTPStatus.UNAUTHORIZED:
            raise meeshkan.exceptions.UnauthorizedRequestException()

        LOGGER.error("Failed requesting authentication: status %s, text: %s", resp.status_code, resp.text)
        raise RuntimeError("Failed requesting authentication.")

    def close(self):
        LOGGER.debug("Closing TokenSource session.")
        self._session.close()


class TokenStore(object):
    """
    Caches authentication tokens, fetches new ones via `fetch_token`
    """
    def __init__(self, fetch_token: FetchToken):
        self._token = None
        self._fetch_token = fetch_token

    def get_token(self, refresh=False):
        if refresh or self._token is None:
            LOGGER.info("Retrieving new authentication token")
            self._token = self._fetch_token()
        return self._token
