from typing import Any
from unittest import mock

import pytest

from client.cloud import Payload, CloudClient
from client.oauth import TokenStore
from client.exceptions import UnauthorizedRequestException
from .utils import MockResponse


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


def _build_session(side_effect):
    session: Any = mock.Mock()
    session.post = mock.MagicMock()
    session.post.side_effect = side_effect
    return session


def test_post_payloads():

    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        headers = kwargs["headers"]
        content = kwargs["json"]
        assert url == _cloud_url()
        assert headers['Authorization'] == 'Bearer 1'
        assert 'query' in content
        return MockResponse(None, 200)

    session = _build_session(side_effect=mocked_requests_post)

    cloud_client = CloudClient(cloud_url=_cloud_url(), token_store=_token_store(), build_session=lambda: session)
    post = cloud_client.post_payload
    payload: Payload = _query_payload()

    with cloud_client:
        post(payload)

    assert session.post.call_count == 1


def test_post_payloads_unauthorized_retry():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        url = args[0]
        headers = kwargs["headers"]
        assert url == _cloud_url()
        assert headers['Authorization'] == f"Bearer {mock_calls}"
        return MockResponse(None, 401) if mock_calls == 1 else MockResponse(None, 200)

    session = _build_session(side_effect=mocked_requests_post)
    cloud_client = CloudClient(cloud_url=_cloud_url(), token_store=_token_store(), build_session=lambda: session)
    post = cloud_client.post_payload
    payload: Payload = _query_payload()

    with cloud_client:
        post(payload)

    assert session.post.call_count == 2  # One failed post and a successful retry


def test_post_payloads_raises_error_for_multiple_401s():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """

    def mocked_requests_post(*args, **kwargs):  # pylint:disable=unused-argument
        return MockResponse(None, 401)

    session = _build_session(side_effect=mocked_requests_post)
    cloud_client = CloudClient(cloud_url=_cloud_url(), token_store=_token_store(), build_session=lambda: session)
    post = cloud_client.post_payload
    payload: Payload = _query_payload()

    with cloud_client, pytest.raises(UnauthorizedRequestException):
        post(payload)

    assert session.post.call_count == 2
