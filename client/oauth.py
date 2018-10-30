from .config import config, secrets
import logging
import json
from typing import Callable, NewType
import requests

logger = logging.getLogger(__name__)

Token = NewType("Token", str)
FetchToken = NewType("FetchToken", Callable[[], Token])


def token_source(auth_url: str, client_id: str, client_secret: str) -> FetchToken:

    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'audience': "https://cloud-api.meeshkan.io",
        "grant_type": "client_credentials"
    }

    def fetch() -> Token:
        resp = requests.post(f"https://{auth_url}/oauth/token", data=payload)
        if resp.status_code == 200:
            resp_dict = resp.json()
            return resp_dict['access_token']
        elif resp.status_code == 401:
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


def main():
    auth_url = config['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    token = token_store.get_token()
    logger.info(f"Got token: {json.dumps(token)}")


if __name__ == '__main__':
    main()
