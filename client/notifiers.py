from .job import Job, ProcessExecutable
from .oauth import TokenStore, token_source, Token
import logging
from .config import config, secrets
from typing import Callable, Dict, Any, NewType
import requests

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


def post_notification(cloud_url: str) -> Callable[[Payload, Token], requests.Response]:
    def post(payload: Payload, token: Token):
        headers = {'Authorization': f"Bearer {token}"}
        return requests.post(f"{cloud_url}", json=payload, headers=headers)
    return post


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
    def __init__(self, token_store: TokenStore, post: Callable[[Payload, Token], requests.Response]):
        super().__init__()
        self._token_store = token_store
        self._post = post

    def notify(self, job: Job) -> None:
        token = self._token_store.get_token()
        query: Payload = build_query_payload(job)
        res = self._post(query, token)
        if res.status_code == 401:  # Unauthorized, try a new token
            token = self._token_store.get_token(refresh=True)
            res = self._post(job, token)
            if res.status_code == 401:
                logger.error('Cannot post to server: unauthorized')
                return
        elif res.status_code != 200:
            raise RuntimeError(f"Got status {res.status_code} with text: {res.text}")
        logger.info(f"Got response {res.text}")
        return


def main():
    auth_url = config['auth']['url']
    client_id = secrets['auth']['client_id']
    client_secret = secrets['auth']['client_secret']
    fetch_token = token_source(auth_url=auth_url, client_id=client_id, client_secret=client_secret)
    token_store = TokenStore(fetch_token=fetch_token)
    post = post_notification(cloud_url=config['cloud']['url'])
    notifier = CloudNotifier(token_store, post=post)
    notifier.notify(Job(ProcessExecutable.from_str("echo hello"), job_id=10))


if __name__ == '__main__':
    main()
