from http import HTTPStatus
import logging
import time
from typing import Any, Callable, List, Optional, Union

from pathlib import Path

import requests

import meeshkan.job
import meeshkan.oauth
import meeshkan.exceptions
import meeshkan.tasks

LOGGER = logging.getLogger(__name__)


class CloudClient:
    """Use for posting payloads to given URL, authenticating with token from token_source.
    Contains retry logic when authorization fails. Raises RuntimeError if server returns other than 200.

    :param cloud_url: URL where to post
    :param token_source: TokenStore instance
    :param build_session: Factory for building sessions (closed with meeshkan.close())
    :raises Unauthorized: if server returns 401
    :raises RuntimeError: If server returns code other than 200 or 401
    """
    def __init__(self, cloud_url: str, token_store: meeshkan.oauth.TokenStore,
                 build_session: Callable[[], requests.Session] = requests.Session):
        self._cloud_url = cloud_url
        self._token_store = token_store
        self._session = build_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _post(self, payload: meeshkan.Payload, token: meeshkan.Token) -> requests.Response:
        headers = {"Authorization": "Bearer {token}".format(token=token)}
        return self._session.post(self._cloud_url, json=payload, headers=headers, timeout=5)

    def _post_payload(self, payload: meeshkan.Payload, retries: int = 1, delay: float = 0.2) -> requests.Response:
        """Post to `cloud_url` with retry: If unauthorized, fetch a new token and retry the given number of times.
        :param payload:
        :param retries:
        :param delay:
        :return:

        :raises meeshkan.exceptions.Unauthorized if received 401 for all retries requested.
        :raises RuntimeError if response status is not OK (not 200 and not 400)
        """
        res = self._post(payload, self._token_store.get_token())
        retries = 1 if retries < 1 else retries  # At least once
        for _ in range(retries):
            if res.status_code != HTTPStatus.UNAUTHORIZED:  # Authed properly
                break
            # Unauthorized, try a new token
            time.sleep(delay)  # Wait to not overload the server
            res = self._post(payload, self._token_store.get_token(refresh=True))
        if res.status_code == HTTPStatus.UNAUTHORIZED:  # Unauthorized for #retries attempts, raise exception
            LOGGER.error('Cannot post to server: unauthorized')
            raise meeshkan.exceptions.UnauthorizedRequestException()
        if res.status_code != HTTPStatus.OK:
            LOGGER.error("Error from server: %s", res.text)
            raise RuntimeError("Post failed with status code {status_code}".format(status_code=res.status_code))
        LOGGER.debug("Got server response: %s", res.text)
        return res

    def post_payload(self, payload: meeshkan.Payload) -> None:
        self._post_payload(payload, delay=0)

    def _upload_file(self, method, url, headers, file):
        """Uploads a file to given URL with method and headers

        :raises RuntimeError on failure
        :return None on success
        """
        res = self._session.request(method, url, headers=headers, files={'': open(file, 'rb')})
        if not res.ok:
            LOGGER.error("Error on file upload: %s", res.text)
            raise RuntimeError("File upload failed with status code {status_code}".format(status_code=res.status_code))

    def post_payload_with_file(self, payload: meeshkan.Payload, file: Union[str, Path]) -> Optional[str]:
        """Post payload to `cloud_url`, followed by a file upload based on the returned values. All without retry.

        Handles schema-negotiation according to
            https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
            (i.e. assumes upload link is given in `upload`, method is `uploadMethod`, and headers in `headers`.

        :param payload
        :param file: string or Path pointing to files to upload
        :return: If `download` is present, returns download link to the uploaded file; otherwise None

        :raises meeshkan.exceptions.Unauthorized if received 401 for all retries requested.
        :raises RuntimeError if response status is not OK (not 200 and not 400)
        """
        res = self._post_payload(payload, retries=1)  # type: Any  # Allow changing types below
        # Parse response
        res = res.json()['data']
        res = res[list(res)[0]]  # Get the first (and only) element within 'data'
        upload_url = res['upload']  # Upload URL
        download_url = res.get('download')  # Final return value; None if does not exist
        upload_method = res['uploadMethod']
        # Convert list of headers to dictionary of headers
        upload_headers = {k.strip(): v.strip() for k, v in [item.split(':') for item in res['headers']]}
        self._upload_file(method=upload_method, url=upload_url, headers=upload_headers, file=file)
        return download_url

    def notify_service_start(self):
        """Build GraphQL query payload and send to server when service is started
        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :return:
        """
        mutation = "mutation ClientStart($in: ClientStartInput!) { clientStart(input: $in) { logLevel } }"
        input_dict = {"version": meeshkan.__version__}
        payload = {"query": mutation, "variables": {"in": input_dict}}
        self.post_payload(payload)

    def pop_tasks(self) -> List[meeshkan.tasks.Task]:
        """Build GraphQL query payload and send to server for new tasks
        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :return:
        """
        mutation = "mutation { popClientTasks { __typename job { id } } }"
        payload = {"query": mutation, "variables": {}}

        res = self._post_payload(payload=payload)

        if not res.ok:
            res.raise_for_status()

        tasks_json = res.json()['data']['popClientTasks']

        def build_task(json_task):
            task_type = meeshkan.tasks.TaskType[json_task['__typename']]
            return meeshkan.tasks.Task(json_task['job']['id'], task_type=task_type)

        tasks = [build_task(json_task) for json_task in tasks_json]
        return tasks

    def close(self):
        LOGGER.debug("Closing CloudClient session")
        self._session.close()
        self._token_store.close()
