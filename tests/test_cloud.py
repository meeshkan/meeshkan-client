from typing import Any
from unittest import mock

import pytest

from meeshkan.cloud import CloudClient
from meeshkan.oauth import TokenStore
from meeshkan.exceptions import UnauthorizedRequestException
from .utils import MockResponse


QUERY_PAYLOAD = {'query': '{ testing }'}
CLOUD_URL = 'https://www.our-favorite-url-yay.fi'


def _build_session(side_effect):
    session: Any = mock.Mock()
    session.post = mock.MagicMock()
    session.post.side_effect = side_effect
    return session


def _mock_token_store():
    return mock.create_autospec(TokenStore)


def test_post_payloads():
    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        headers = kwargs["headers"]
        content = kwargs["json"]
        assert url == CLOUD_URL
        assert headers['Authorization'].startswith('Bearer')  # TokenStore is checked in test_oauth
        assert 'query' in content
        return MockResponse(None, 200)

    session = _build_session(side_effect=mocked_requests_post)
    mock_store = _mock_token_store()

    with CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session) as cloud_client:
        cloud_client.post_payload(QUERY_PAYLOAD)

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
        assert url == CLOUD_URL
        assert headers['Authorization'].startswith("Bearer")
        return MockResponse(None, 401) if mock_calls == 1 else MockResponse(None, 200)

    session = _build_session(side_effect=mocked_requests_post)
    mock_store = _mock_token_store()

    with CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session) as cloud_client:
        cloud_client.post_payload(QUERY_PAYLOAD)

    assert session.post.call_count == mock_calls  # One failed post and a successful retry


def test_post_payloads_raises_error_for_multiple_401s():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """

    def mocked_requests_post(*args, **kwargs):  # pylint:disable=unused-argument
        return MockResponse(None, 401)

    session = _build_session(side_effect=mocked_requests_post)
    mock_store = _mock_token_store()
    cloud_client = CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session)

    with cloud_client, pytest.raises(UnauthorizedRequestException):
        cloud_client.post_payload(QUERY_PAYLOAD)

    assert session.post.call_count == 2
