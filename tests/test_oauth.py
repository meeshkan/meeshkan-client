from typing import Any
from unittest import mock

import pytest
import requests

from meeshkan.oauth import TokenStore, TokenSource
from .utils import MockResponse


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


def test_token_store():
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
    token_store = TokenStore(fetch_token=fetch_token)

    assert token_store.get_token() == '1'
    assert token_store.get_token() == '1' # From cache
    assert token_store.get_token(refresh=True) == '2'
    assert token_store.get_token() == '2'


def _auth_url():
    return 'favorite-url-yay.com'


def _client_id():
    return 'meeshkan-id-1'


def _client_secret():
    return 'meeshkan-top-secret'


def _token_response():
    return {'access_token': 'token'}


def test_token_source():

    session: requests.Session = mock.Mock(spec=requests.Session)

    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        assert url == f"https://{_auth_url()}/oauth/token"
        payload = kwargs['data']
        assert payload['client_id'] == _client_id()
        assert payload['client_secret'] == _client_secret()
        assert payload['audience'] == "https://api.meeshkan.io"
        assert payload['grant_type'] == "client_credentials"
        return MockResponse(_token_response(), 200)

    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post

    with TokenSource(
         auth_url=_auth_url(), client_id=_client_id(), client_secret=_client_secret(), build_session=lambda: session)\
            as token_source:
        token = token_source.fetch_token()
        assert token == _token_response()['access_token']

    assert session.post.call_count == 1


def test_token_source_raises_error_for_non_200():

    session: Any = mock.Mock(spec=requests.Session)

    def mocked_requests_post(*args, **kwargs):
        return MockResponse(_token_response(), 201)

    session.post = mock.MagicMock()
    session.post.side_effect = mocked_requests_post

    with pytest.raises(RuntimeError), \
        TokenSource(auth_url=_auth_url(), client_id=_client_id(), client_secret=_client_secret(),
                    build_session=lambda: session) as token_source:
        token_source.fetch_token()

    session.post.assert_called()

    assert session.post.call_count == 1
