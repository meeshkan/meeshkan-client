import client
from client.oauth import TokenStore, token_source
from .test_notifiers import _MockResponse
import pytest
from unittest import mock


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
    return 'client-id-1'


def _client_secret():
    return 'client-top-secret'


def _token_response():
    return {'access_token': 'token'}


def test_token_source():

    fetch_token = token_source(auth_url=_auth_url(), client_id=_client_id(), client_secret=_client_secret())

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        url = args[0]
        assert url == f"https://{_auth_url()}/oauth/token"
        payload = kwargs['data']
        assert payload['client_id'] == _client_id()
        assert payload['client_secret'] == _client_secret()
        assert payload['audience'] == "https://api.meeshkan.io"
        assert payload['grant_type'] == "client_credentials"
        return _MockResponse(_token_response(), 200)

    with mock.patch('requests.post', side_effect=mocked_requests_post):
        token = fetch_token()
        assert token == _token_response()['access_token']

    assert mock_calls == 1


def test_token_source_raises_error_for_non_200():

    fetch_token = token_source(auth_url=_auth_url(), client_id=_client_id(), client_secret=_client_secret())

    mock_calls = 0

    def mocked_requests_post(*args, **kwargs):
        nonlocal mock_calls
        mock_calls += 1
        return _MockResponse(_token_response(), 201)

    with pytest.raises(RuntimeError), mock.patch('requests.post', side_effect=mocked_requests_post):
        fetch_token()

    assert mock_calls == 1
