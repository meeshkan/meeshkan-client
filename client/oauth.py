from http import HTTPStatus
import logging
import requests
from typing import Callable, NewType

logger = logging.getLogger(__name__)

Token = NewType("Token", str)
FetchToken = NewType("FetchToken", Callable[[], Token])


def token_source(auth_url: str, client_id: str, client_secret: str) -> FetchToken:

    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'audience': "https://api.meeshkan.io",
        "grant_type": "client_credentials"
    }

    def fetch() -> Token:
        resp = requests.post(f"https://{auth_url}/oauth/token", data=payload)
        if resp.status_code == HTTPStatus.OK:
            resp_dict = resp.json()
            return resp_dict['access_token']
        elif resp.status_code == HTTPStatus.UNAUTHORIZED:
            raise RuntimeError("Failed requesting authentication. Check your credentials.")
        else:
            logger.error(f"Failed requesting authentication, got response with status {resp.status_code}.")
            raise RuntimeError("Failed requesting authentication.")
    return fetch


class TokenStore(object):
    """
    Caches authentication tokens, fetches new ones via `fetch_token`
    """
    def __init__(self, fetch_token: FetchToken):
        self._token = None
        self._fetch_token = fetch_token

    def get_token(self, refresh=False):
        if refresh or self._token is None:
            logger.info("Retrieving new authentication token")
            self._token = self._fetch_token()
        return self._token
