from typing import Any
from unittest import mock

import pytest
import requests

from meeshkan.oauth import TokenStore
from .utils import MockResponse

_auth_url = 'favorite-url-yay.com'
_client_id = 'meeshkan-id-1'
_client_secret = 'meeshkan-top-secret'
_token_response = {'access_token': 'token'}

def _token_store(build_session=None):
    """Returns a TokenStore for unit testing"""
    if build_session is None:
        return TokenStore(auth_url=_auth_url, client_id=_client_id, client_secret=_client_secret)
    return TokenStore(auth_url=_auth_url, client_id=_client_id, client_secret=_client_secret, build_session=build_session)


def test_token_store():
    def _get_fetch_token():
        """
        :return: Function returning tokens that increment by one for every call
        """
        requests_counter = 0

        def fetch(self):
            nonlocal requests_counter
            requests_counter += 1
            return str(requests_counter)

        return fetch

    with mock.patch('meeshkan.oauth.TokenStore._fetch_token', _get_fetch_token()):  # Override default _fetch_token
        with _token_store() as token_store:
            assert token_store.get_token() == '1'
            assert token_store.get_token() == '1' # From cache
            assert token_store.get_token(refresh=True) == '2'
            assert token_store.get_token() == '2'


def test_token_source():
    session: requests.Session = mock.Mock(spec=requests.Session)  # Mock session
    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        assert url == "https://{url}/oauth/token".format(url=_auth_url)
        payload = kwargs['data']
        assert payload['client_id'] == _client_id
        assert payload['client_secret'] == _client_secret
        assert payload['audience'] == "https://api.meeshkan.io"
        assert payload['grant_type'] == "client_credentials"
        return MockResponse(_token_response, 200)
    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post

    with _token_store(build_session=lambda: session) as token_store:
        token = token_store.get_token()
        assert token == _token_response['access_token']

    assert session.post.call_count == 1


def test_token_source_raises_error_for_non_200():
    def mocked_requests_post(*args, **kwargs):
        return MockResponse(_token_response, 201)
    session: Any = mock.Mock(spec=requests.Session)
    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post
    with pytest.raises(RuntimeError), _token_store(build_session=lambda: session) as token_store:
        token_store.get_token()
    session.post.assert_called()
    assert session.post.call_count == 1
