from http import HTTPStatus
import logging
from typing import Callable, Dict, NewType
import requests

import client.job
import client.oauth
import client.exceptions

LOGGER = logging.getLogger(__name__)

Payload = NewType('Payload', Dict[str, str])


class CloudClient:
    """
        Use for posting payloads to given URL, authenticating with token from token_store.
        Contains retry logic when authorization fails. Raises RuntimeError if server returns other than 200.
        :param cloud_url: URL where to post
        :param token_store: TokenStore instance
        :param build_session: Factory for building sessions (closed with client.close())
        :raises Unauthorized: if server returns 401
        :raises RuntimeError: If server returns code other than 200 or 401
        """
    def __init__(self, cloud_url: str, token_store: client.oauth.TokenStore,
                 build_session: Callable[[], requests.Session]):
        self._cloud_url = cloud_url
        self._token_store = token_store
        self._session = build_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _post(self, payload: Payload, token: client.oauth.Token) -> requests.Response:
        headers = {'Authorization': f"Bearer {token}"}
        return self._session.post(self._cloud_url, json=payload, headers=headers, timeout=5)

    def post_payload(self, payload: Payload) -> None:
        """
        Post to `cloud_url` with retry: If unauthorized, fetch a new token and retry (once).
        :param payload:
        :raises client.exceptions.Unauthorized if received 401 twice.
        :return:
        """
        token = self._token_store.get_token()
        res = self._post(payload, token)
        if res.status_code == HTTPStatus.UNAUTHORIZED:  # Unauthorized, try a new token
            token = self._token_store.get_token(refresh=True)
            res = self._post(payload, token)
            if res.status_code == HTTPStatus.UNAUTHORIZED:
                LOGGER.error('Cannot post to server: unauthorized')
                raise client.exceptions.Unauthorized()
        if res.status_code != HTTPStatus.OK:
            LOGGER.error("Error from server: %s", res.text)
            raise RuntimeError(f"Post failed with status code {res.status_code}")
        LOGGER.debug("Got server response: %s", res.text)

    def notify_service_start(self):
        self.post_payload(_build_service_start_payload())

    def close(self):
        LOGGER.debug("Closing CloudClient session")
        self._session.close()


def _build_service_start_payload() -> Payload:
    """
    Build GraphQL query payload to be sent to server when service is started
    Schema of job_input MUST match with the server schema
    https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
    :return:
    """
    mutation = "mutation ClientStart($in: ClientStartInput!) { clientStart(input: $in) { logLevel } }"

    input_dict = {
        "version": client.__version__
    }
    payload: Payload = {
        "query": mutation,
        "variables": {
            "in": input_dict
        }
    }
    return payload
