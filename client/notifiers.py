""" Notifiers for changes in job status"""
from http import HTTPStatus
import logging
from typing import Callable, Dict, NewType
import requests

import client.job
import client.oauth

LOGGER = logging.getLogger(__name__)

Payload = NewType('Payload', Dict[str, str])


class Notifier(object):

    def __init__(self):
        pass

    def notify(self, job: client.job.Job) -> None:
        """
        Notifies job status. Raises exception for failure.
        :param job:
        :return:
        """
        pass


def post_payloads(cloud_url: str, token_store: client.oauth.TokenStore) -> Callable[[Payload], None]:
    """
    Return a function posting payloads to given URL, authenticating with token from token_store.
    Contains retry logic when authorization fails. Raises RuntimeError if server returns other than 200.
    :param cloud_url: URL where to post
    :param token_store: TokenStore instance
    :raises RuntimeError: if server returns a code other than 200
    :return: Function for posting payload
    """
    def _post(payload: Payload, token: client.oauth.Token) -> requests.Response:
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
                LOGGER.error('Cannot post to server: unauthorized')
                raise RuntimeError("Cannot post: Unauthorized")
        if res.status_code != HTTPStatus.OK:
            LOGGER.error("Error from server: %s", res.text)
            raise RuntimeError(f"Post failed with status code {res.status_code}")
        LOGGER.info(res.text)
    return post_with_retry


def _build_query_payload(job: client.job.Job) -> Payload:
    mutation = "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"
    payload: Payload = {
        "query": mutation,
        "variables": {
            "in": {
                "id": str(job.id),
                "name": "name",
                "number": job.number,
                "created": job.created.isoformat() + "Z",  # Assume it's UTC
                "description": "description",
                "message": str(job.status)
            }
        }
    }
    return payload


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: client.job.Job) -> None:
        query_payload: Payload = _build_query_payload(job)
        self._post_payload(query_payload)
        LOGGER.info(f"Posted successfully: %s", str(job))
