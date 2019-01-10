import time
from http import HTTPStatus
from typing import Callable
from unittest import mock

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

