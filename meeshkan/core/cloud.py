import logging
import time
from typing import Callable, List, Optional, Union
from uuid import UUID

from pathlib import Path

import requests

from ..__types__ import Token, Payload
from .tasks import TaskType, Task
from .oauth import TokenStore
from ..exceptions import UnauthorizedRequestException
from ..__version__ import __version__

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]

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
    def __init__(self, cloud_url: str, token_store: TokenStore = None,
                 refresh_token: str = None,
                 build_session: Callable[[], requests.Session] = requests.Session):
        self._cloud_url = cloud_url
        if token_store is not None:
            self._token_store = token_store
        elif refresh_token is not None:
            self._token_store = CloudTokenStore(self, refresh_token)
        else:
            raise RuntimeError("Can't instantiate a CloudClient without either TokenStore or refresh token")
        self._session = build_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _post(self, payload: Payload, token: Token = None) -> requests.Response:
        headers = {"Authorization": "Bearer {token}".format(token=token)} if token is not None else None
        return self._session.post(self._cloud_url, json=payload, headers=headers, timeout=5)

    @staticmethod
    def _check_for_errors(res):
        """
        Check GraphQL response body for errors.
        :param res: GraphQL response
        :raises meeshkan.exceptions.Unauthorized if one of errors was "UNAUTHENTICATED"
        :raises RuntimeError if there were any other errors
        :return: None
        """

        if not res.ok:
            LOGGER.error("Error from server: %s", res.text)
            res.raise_for_status()

        body = res.json()
        errors = body.get("errors", list())

        if not errors:
            return

        def contains_unauthenticated(errs):
            for err in errs:
                code = err.get("extensions", {}).get("code", "")
                if code == "UNAUTHENTICATED":
                    return True
            return False

        if contains_unauthenticated(errors):
            LOGGER.error('Could not post to server: unauthenticated')
            raise UnauthorizedRequestException()

        LOGGER.error("Unknown error from server: %s", res.text)
        raise RuntimeError("Error posting to server")

    def _post_gql_payload(self, payload: Payload, retries: int = 1, delay: float = 0.2) -> dict:
        """Post to `cloud_url` with retry: If unauthenticated, fetch a new token and retry the given number of times.
        Checks that the response does not contain any errors, raises error if yes.
        :param payload:
        :param retries:
        :param delay:
        :return: GraphQL response data
        :raises meeshkan.exceptions.Unauthorized if received UNAUTHENTICATED for all retries requested.
        :raises RuntimeError if response status is not OK (not 200 and not 400)
        """

        token = self._token_store.get_token()

        retries = max(1, retries)  # At least once

        for try_count in range(retries + 1):
            time.sleep(try_count * delay)  # Wait to not overload the server

            res = self._post(payload, token)

            LOGGER.debug("Got response from server: %s, status %d", res.text, res.status_code)

            try:
                CloudClient._check_for_errors(res)
                return res.json()['data']
            except UnauthorizedRequestException:  # Raise other errors
                token = self._token_store.get_token(refresh=True)

        raise UnauthorizedRequestException

    def post_payload(self, payload: Payload) -> None:
        self._post_gql_payload(payload)

    def get_new_token(self, refresh_token: str) -> Token:
        query = "query GetToken($refresh_token: String!) { token(refreshToken: $refresh_token) { access_token } }"
        payload = {"query": query, "variables": {"refresh_token": refresh_token}}  # type: Payload
        res = self._post(payload)
        CloudClient._check_for_errors(res)
        return res.json()['data']['token']['access_token']

    def _upload_file(self, method, url, headers, file):
        """Uploads a file to given URL with method and headers

        :raises RuntimeError on failure
        :return None on success
        """
        res = self._session.request(method, url, headers=headers, data=open(file, 'rb').read())
        if not res.ok:
            LOGGER.error("Error on file upload: %s", res.text)
            raise RuntimeError("File upload failed with status code {status_code}".format(status_code=res.status_code))
        LOGGER.debug("Uploading file, got response %s", res)

    def post_payload_with_file(self, file: Union[str, Path], download_link=False) -> Optional[str]:
        """Uploads a file to `cloud_url`, fetching a download link if needed. All without retry.

        Handles schema-negotiation according to
            https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
            (i.e. assumes upload link is given in `upload`, method is `uploadMethod`, and headers in `headers`.

        :param file: string or Path pointing to files to upload
        :param download_link: whether or not to ask for a download link
        :return: download link if requested, otherwise None

        :raises meeshkan.exceptions.Unauthorized if received 401 for all retries requested.
        :raises RuntimeError if response status is not OK
        """
        file = str(file)  # Removes dependency on Path or str
        query = "query ($ext: String!, $download_flag: Boolean) {" \
                  "uploadLink(extension: $ext, download_link: $download_flag) {" \
                    "upload, download, headers, uploadMethod" \
                  "}" \
                "}"
        extension = "".join(Path(file).suffixes)[1:]  # Extension(s), and remove prefix dot...
        payload = {"query": query,
                   "variables": {"ext": extension, "download_flag": download_link}}  # type: Payload
        res = self._post_gql_payload(payload)

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
        input_dict = {"version": __version__}
        payload = {"query": mutation, "variables": {"in": input_dict}}
        self.post_payload(payload)

    def pop_tasks(self) -> List[Task]:
        """Build GraphQL query payload and send to server for new tasks
        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :return:
        """
        mutation = "mutation { popClientTasks { __typename job { id } } }"
        payload = {"query": mutation, "variables": {}}

        data = self._post_gql_payload(payload=payload)

        tasks_json = data['popClientTasks']

        def build_task(json_task):
            task_type = TaskType[json_task['__typename']]
            return Task(UUID(json_task['job']['id']), task_type=task_type)

        tasks = [build_task(json_task) for json_task in tasks_json]
        return tasks

    def close(self):
        LOGGER.debug("Closing CloudClient session")
        self._session.close()


class CloudTokenStore(TokenStore):
    def __init__(self, client: CloudClient, refresh_token: str):
        super().__init__(refresh_token)
        self._client = client

    def _fetch_token(self) -> Token:
        LOGGER.debug("Requesting new token")
        try:
            return self._client.get_new_token(self._refresh_token)
        except UnauthorizedRequestException:
            raise RuntimeError("Failed requesting authentication.")
