from unittest import mock

import pytest

from client.notifiers import CloudNotifier, Payload, post_payloads
from client.oauth import TokenStore
from client.job import Job, Executable
from client.exceptions import UnauthorizedRequestError


def _get_job():
    return Job(Executable(), job_number=0)


def test_cloud_notifier():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    assert posted_payload == {}
    cloud_notifier = CloudNotifier(fake_post)
    cloud_notifier.notify(_get_job())

    expected_payload = {"query": "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"}

    assert "query" in posted_payload

    assert posted_payload["query"] == expected_payload["query"]

    assert "variables" in posted_payload
    variables = posted_payload["variables"]
    assert "in" in variables


def test_cloud_notifier_propagates_exception():
    def fake_post(payload):
        raise RuntimeError("Boom!")

    cloud_notifier = CloudNotifier(fake_post)
    with pytest.raises(RuntimeError):
        cloud_notifier.notify(_get_job())


class _MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    @property
    def text(self):
        return "Mock response"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def _query_payload():
    return {'query': '{ testing }'}


def _cloud_url():
    return 'https://www.our-favorite-url-yay.fi'


def _token_store():
    def _get_fetch_token():
        """
        :return: Function returning tokens that increment by one for every call
        """
        requests_counter = 0

        def fetch():
            nonlocal requests_counter
            requests_counter += 1
            return str(requests_counter)

        return fetch
    fetch_token = _get_fetch_token()
    return TokenStore(fetch_token=fetch_token)


def test_post_payloads():
    post = post_payloads(cloud_url=_cloud_url(), token_store=_token_store())
    payload: Payload = _query_payload()

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        url = args[0]
        headers = kwargs["headers"]
        content = kwargs["json"]
        assert url == _cloud_url()
        assert headers['Authorization'] == 'Bearer 1'
        assert 'query' in content
        return _MockResponse(None, 200)

    with mock.patch('requests.post', side_effect=mocked_requests_post):
        post(payload)

    assert mock_calls == 1


def test_post_payloads_unauthorized_retry():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """
    post = post_payloads(cloud_url=_cloud_url(), token_store=_token_store())
    payload: Payload = _query_payload()

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        url = args[0]
        headers = kwargs["headers"]
        assert url == _cloud_url()
        assert headers['Authorization'] == f"Bearer {mock_calls}"
        return _MockResponse(None, 401) if mock_calls == 1 else _MockResponse(None, 200)

    with mock.patch('requests.post', side_effect=mocked_requests_post):
        post(payload)

    assert mock_calls == 2  # One failed post and a successful retry


def test_post_payloads_raises_error_for_multiple_401s():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """
    post = post_payloads(cloud_url=_cloud_url(), token_store=_token_store())
    payload: Payload = _query_payload()

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        return _MockResponse(None, 401)

    with mock.patch('requests.post', side_effect=mocked_requests_post), pytest.raises(UnauthorizedRequestError):
        post(payload)

    assert mock_calls == 2  # Two (failed) calls
