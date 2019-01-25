import time
from http import HTTPStatus
from typing import Callable
from unittest import mock
from typing import Optional
import sys
import subprocess

from IPython.terminal.ipapp import launch_new_instance
from notebook.auth import passwd
import requests
from meeshkan.notifications.notifiers import Notifier
from meeshkan.core.job import Job
from meeshkan.core.oauth import TokenStore
from meeshkan.__types__ import Token

FUTURE_TIMEOUT = 10  # In seconds


# https://github.com/testing-cabal/mock/issues/139
class PicklableMock(mock.MagicMock):
    def __reduce__(self):
        return (mock.MagicMock, ())


class MockResponse(object):
    def __init__(self, json_data=None, status_code=None):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def text(self):
        return "Mock response"

    @property
    def ok(self):
        return self.status_code == 200

    def raise_for_status(self):
        raise RuntimeError("Raised for status {status}".format(status=self.status_code))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def for_unauthenticated():
        return MockResponse({"errors": [{"extensions": {"code": "UNAUTHENTICATED"}}]}, 200)


class DummyStore(TokenStore):
    def __init__(self, cloud_url: str, refresh_token: str,
                 build_session: Callable[[], requests.Session] = None):
        super(DummyStore, self).__init__(refresh_token)
        self._auth_url = cloud_url
        self._session = build_session() if build_session is not None else None
        self.requests_counter = 0
        query = "query GetToken($refresh_token: String!) { token(refreshToken: $refresh_token) { access_token } }"
        self._payload = {"query": query, "variables": {"refresh_token": refresh_token}}  # type: Payload

    def _fetch_token(self) -> Token:
        if self._session is not None:
            resp = self._session.post(self._auth_url, json=self._payload, timeout=15)
            if resp.status_code == HTTPStatus.OK:
                resp_dict = resp.json()['data']
                return resp_dict['token']['access_token']
            if resp.status_code == HTTPStatus.UNAUTHORIZED:
                raise UnauthorizedRequestException()
            raise RuntimeError("Failed requesting authentication.")
        else:
            self.requests_counter += 1
            return Token(str(self.requests_counter))


class MockNotifier(Notifier):
    def __init__(self):
        super().__init__()
        self.finished_jobs = []
        self.notified_jobs = []
        self.started_jobs = []

    def _notify_job_start(self, job: Job):
        self.started_jobs.append({'job': job})

    def _notify_job_end(self, job: Job):
        self.finished_jobs.append({'job': job})

    def _notify(self, job: Job, image_url: str, n_iterations: int = -1, iterations_unit: str = "iterations") -> None:
        self.notified_jobs.append({'job': job})


def wait_for_true(func, timeout=FUTURE_TIMEOUT):
    slept = 0
    time_to_sleep = 0.1
    while not func():
        time.sleep(time_to_sleep)
        slept += time_to_sleep
        if slept > timeout:
            raise Exception("Wait timeout for func {func}".format(func=func))


class NBServer:
    def __init__(self, ip: str, port: int, key: str = "", use_password: bool = False):
        self.ip = ip
        self.port = port
        self.key = key
        self.use_password = use_password
        self.server = None  # type: Optional[subprocess.Popen]

    @property
    def url(self):
        return "http://{ip}:{port}/".format(ip=self.ip, port=self.port)

    def __enter__(self):
        self._start_local_jupyter_server()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server is not None:
            self.server.terminate()
            self.server = None

    def _start_local_jupyter_server(self):
        """Starts a local instance of a jupyter notebook server with given key as token or password.
        It is up to the calling method to terminate the process.
        """
        if self.use_password:
            notebook_security = "'--NotebookApp.password={password}'".format(password=passwd(self.key))
        else:
            notebook_security = "'--NotebookApp.token={token}'".format(token=self.key)
        self.server = subprocess.Popen(["python", "-c", "from IPython.terminal.ipapp import launch_new_instance; "
                                                         "import sys;"
                                                         "sys.argv = ['jupyter', 'notebook', "
                                                                     "'--IPKernelApp.pylab=inline', "
                                                                     "'--NotebookApp.open_browser=False', {security}, "
                                                                     "'--NotebookApp.port={port}', "
                                                                     "'--NotebookApp.ip={ip}', "
                                                                     "'--NotebookApp.log_level=CRITICAL'];"
                                                         "launch_new_instance()".format(ip=self.ip, port=self.port,
                                                                                        security=notebook_security)],
                                       stdout=subprocess.PIPE)
        if self.server.poll() is not None:
            raise RuntimeError("Could not start jupyter notebook!")

        # Wait until server is up:
        server_is_up = False
        sleep_time = 0.1  # seconds between polling for process to finish
        while not server_is_up:
            check_server_proc = subprocess.Popen(["jupyter", "notebook", "list"], stdout=subprocess.PIPE)
            while check_server_proc.poll() is None:  # Process is still ongoing
                time.sleep(sleep_time)
            server_is_up = self.url in check_server_proc.stdout.read().decode()