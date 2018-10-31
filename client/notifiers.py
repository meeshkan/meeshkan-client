from .job import Job, ProcessExecutable
from .oauth import TokenStore, token_source, Token
import logging
from .config import config, secrets
from typing import Callable, Dict, NewType
import requests
from http import HTTPStatus

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


def build_query_payload(job: Job) -> Payload:
    query = "{ hello }"
    payload: Payload = {
        "query": query,
        # "variables": {
        #     "id": job.id
        # }
    }
    return payload


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: Job) -> None:
        query_payload: Payload = build_query_payload(job)
        self._post_payload(query_payload)
        logger.info(f"Posted successfully: {job}")
        return


def main():
    auth_url = config['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post_payload = post_payloads(cloud_url=config['cloud']['url'], token_store=token_store)
    notifier = CloudNotifier(post_payload=post_payload)
    notifier.notify(Job(ProcessExecutable.from_str("echo hello"), job_id=10))


if __name__ == '__main__':
    main()
