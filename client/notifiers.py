""" Notifiers for changes in job status"""
from http import HTTPStatus
import logging
from typing import Callable, Dict, NewType
import requests

import client.job
import client.oauth
import client.exceptions

from client.version import __version__ as version

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

    def close(self):
        LOGGER.debug("Closing CloudClient session")
        self._session.close()


def _build_job_notify_payload(job: client.job.Job) -> Payload:
    """
    Build GraphQL query payload to be sent to server.
    Schema of job_input MUST match with the server schema
    https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
    :param job:
    :return:
    """
    mutation = "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"

    job_input = {
        "id": str(job.id),
        "name": "name",
        "number": job.number,
        "created": job.created.isoformat() + "Z",  # Assume it's UTC
        "description": "description",
        "message": str(job.status)
    }
    payload: Payload = {
        "query": mutation,
        "variables": {
            "in": job_input
        }
    }
    return payload


def _build_service_start_payload() -> Payload:
    """
    Build GraphQL query payload to be sent to server when service is started
    Schema of job_input MUST match with the server schema
    https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
    :return:
    """
    mutation = "mutation ClientStart($in: ClientStartInput!) { clientStart(input: $in) { logLevel } }"

    input_dict = {
        "version": version
    }
    payload: Payload = {
        "query": mutation,
        "variables": {
            "in": input_dict
        }
    }
    return payload


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: client.job.Job) -> None:
        query_payload: Payload = _build_job_notify_payload(job)
        self._post_payload(query_payload)
        LOGGER.info(f"Posted successfully: %s", str(job))

    def notify_service_start(self):
        self._post_payload(_build_service_start_payload())
