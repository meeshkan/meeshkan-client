from http import HTTPStatus
from unittest import mock
import uuid

import pytest
import requests

from meeshkan.core.oauth import TokenStore
from meeshkan.core.cloud import CloudClient
from meeshkan.exceptions import UnauthorizedRequestException
from .utils import MockResponse


QUERY_PAYLOAD = {'query': '{ testing }'}
CLOUD_URL = 'https://www.our-favorite-url-yay.fi'


def _build_session(post_side_effect=None):
    session = mock.create_autospec(requests.Session)
    if post_side_effect:
        session.post.side_effect = post_side_effect
    return session


def _mock_token_store():
    return mock.create_autospec(TokenStore)


def test_post_payloads():
    def mocked_requests_post(*args, **kwargs):
        url = args[0]
        headers = kwargs["headers"]
        content = kwargs["json"]
        assert url == CLOUD_URL, "Expecting query URL to match '{}'".format(CLOUD_URL)
        # TokenStore is checked in test_oauth
        assert headers['Authorization'].startswith('Bearer'), "Expects the 'Bearer' keyword in beginning of " \
                                                              "'Authorization' header"
        assert 'query' in content, "Expected content of GraphQL payload to contain keyword 'query'"
        return MockResponse({"data": {}}, 200)

    session = _build_session(post_side_effect=mocked_requests_post)
    mock_store = _mock_token_store()

    with CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session) as cloud_client:
        cloud_client.post_payload(QUERY_PAYLOAD)

    assert session.post.call_count == 1, "Mock `post` was only called once"


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
        assert url == CLOUD_URL, "Expecting query URL to match '{}'".format(CLOUD_URL)
        assert headers['Authorization'].startswith("Bearer"), "Expects the 'Bearer' keyword in beginning of " \
                                                              "'Authorization' header"
        if mock_calls == 1:
            return MockResponse.for_unauthenticated()

        return MockResponse({"data": {}}, 200)

    session = _build_session(post_side_effect=mocked_requests_post)
    mock_store = _mock_token_store()

    with CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session) as cloud_client:
        cloud_client.post_payload(QUERY_PAYLOAD)

    assert session.post.call_count == mock_calls, "Mock `post` was called only {} times " \
                                                  "(fail and success)".format(mock_calls)


def test_post_payloads_raises_error_for_multiple_401s():
    """
    Test authorization retry logic. If post returns 401, poster should retry with a new token.
    :return:
    """

    def mocked_requests_post(*args, **kwargs):  # pylint:disable=unused-argument
        return MockResponse.for_unauthenticated()

    session = _build_session(post_side_effect=mocked_requests_post)
    mock_store = _mock_token_store()
    cloud_client = CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: session)

    with cloud_client, pytest.raises(UnauthorizedRequestException):
        cloud_client.post_payload(QUERY_PAYLOAD)

    assert session.post.call_count == 2, "Posting a payload should raise an error after being called TWICE at most " \
                                         "(by default)."


def test_pop_tasks():
    mock_session = mock.create_autospec(requests.Session, spec_set=True)

    job_id = str(uuid.uuid4())
    task_name = 'StopJobTask'

    returned_task = {'job': {'job_id': str(job_id)}, '__typename': task_name}

    mock_session.post.return_value = MockResponse(status_code=HTTPStatus.OK,
                                                  json_data={'data': {'popClientTasksV2': [returned_task]}})

    mock_store = mock.create_autospec(TokenStore, spec_set=True)

    cloud_client = CloudClient(cloud_url=CLOUD_URL, token_store=mock_store, build_session=lambda: mock_session)

    with cloud_client:
        tasks = cloud_client.pop_tasks()

    mock_session.post.assert_called_once()

    assert len(tasks) == 1, "Hard-coded GraphQL query returns a strict single-item list. What happened?"
    created_task = tasks[0]

    assert created_task.job_identifier == job_id, "The job ID for the task should reflect the original job_id after " \
                                                  "creating a proper Task object"
    assert created_task.type.name == task_name, "The task typename should match the original typename after creating " \
                                                "a proper Task object"
