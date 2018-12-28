from typing import Any
from unittest import mock

import pytest
import requests

from meeshkan.core.oauth import TokenStore
from .utils import MockResponse, DummyStore

CLOUD_URL = 'https://favorite-url-yay.com'
REFRESH_TOKEN = 'meeshkan-top-secret'
TOKEN_RESPONSE = { "data": { "token": { "access_token": "token" } } }

def _token_store(build_session=None):
    """Returns a TokenStore for unit testing"""
    if build_session is None:
        return DummyStore(cloud_url=CLOUD_URL, refresh_token=REFRESH_TOKEN)
    return DummyStore(cloud_url=CLOUD_URL, refresh_token=REFRESH_TOKEN, build_session=build_session)


def test_token_store():
    token_store = _token_store()
    assert token_store.get_token() == '1'
    assert token_store.get_token() == '1'  # From cache
    assert token_store.get_token(refresh=True) == '2'
    assert token_store.get_token() == '2'


def test_token_source():
    session: requests.Session = mock.Mock(spec=requests.Session)  # Mock session

    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        assert url == CLOUD_URL
        payload = kwargs['json']
        vars = payload['variables']
        assert vars['refresh_token'] == REFRESH_TOKEN
        return MockResponse(TOKEN_RESPONSE, 200)

    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post

    token_store = _token_store(build_session=lambda: session)
    token = token_store.get_token()
    assert token == TOKEN_RESPONSE['data']['token']['access_token']
    assert session.post.call_count == 1


def test_token_source_raises_error_for_non_200():
    def mocked_requests_post(*args, **kwargs):   # pylint: disable=unused-argument
        return MockResponse(TOKEN_RESPONSE, 201)
    session: Any = mock.Mock(spec=requests.Session)
    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post
    token_store = _token_store(build_session=lambda: session)
    with pytest.raises(RuntimeError):
        token_store.get_token()
    session.post.assert_called()
    assert session.post.call_count == 1
