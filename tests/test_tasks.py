from unittest.mock import create_autospec

import requests
import pytest

from meeshkan.tasks import TaskPoller, TaskSource


def _mock_session():
    return create_autospec(requests.Session).return_value


def test_task_source_closes_session():

    mock_session = _mock_session()
    task_source = TaskSource(build_session=lambda: mock_session)
    mock_session.close.assert_not_called()
    with task_source:
        pass
    mock_session.close.assert_called()


@pytest.mark.asyncio
async def test_task_source_returns_tasks():

    task_source = TaskSource(build_session=_mock_session)
    with task_source:
        tasks = await task_source.pop_tasks()

    assert len(tasks) == 1

