from client.job import Job
from client.oauth import TokenStore, Token
from http import HTTPStatus
import logging
import requests
from typing import Callable, Dict, NewType


logger = logging.getLogger(__name__)

Payload = NewType('Payload', Dict[str, str])


class Notifier(object):

    def __init__(self):
        pass

    def notify(self, job: Job) -> None:
        """
        Notifies job status. Raises exception for failure.
        :param job:
        :return:
        """
        pass


def post_payloads(cloud_url: str, token_store: TokenStore) -> Callable[[Payload], None]:
    """
    Return a function posting payloads to given URL, authenticating with token from token_store.
    Contains retry logic when authorization fails. Raises RuntimeError if server returns other than 200.
    :param cloud_url: URL where to post
    :param token_store: TokenStore instance
    :raises RuntimeError: if server returns a code other than 200
    :return: Function for posting payload
    """
    def _post(payload: Payload, token: Token) -> requests.Response:
        headers = {'Authorization': f"Bearer {token}"}
        return requests.post(f"{cloud_url}", json=payload, headers=headers)

    def post_with_retry(payload: Payload) -> None:
        """
        Post to `cloud_url` with retry: If unauthorized, fetch a new token and retry (once).
        """
        token = token_store.get_token()
        res = _post(payload, token)
        if res.status_code == HTTPStatus.UNAUTHORIZED:  # Unauthorized, try a new token
            token = token_store.get_token(refresh=True)
            res = _post(payload, token)
            if res.status_code == HTTPStatus.UNAUTHORIZED:
                logger.error('Cannot post to server: unauthorized')
                raise RuntimeError("Cannot post: Unauthorized")
        if res.status_code != HTTPStatus.OK:
            raise RuntimeError(f"Post failed with status code {res.status_code}")
        return
    return post_with_retry


def _build_query_payload(job: Job) -> Payload:
    query = "{ hello }"
    payload: Payload = {
        "query": query
    }
    return payload


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: Job) -> None:
        query_payload: Payload = _build_query_payload(job)
        self._post_payload(query_payload)
        logger.info(f"Posted successfully: {job}")
        return
