import asyncio
import concurrent.futures
import queue
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


@pytest.mark.asyncio
async def test_task_poller_handles_tasks():

    def mock_task_source(returned_task):
        mock_task_source = create_autospec(TaskSource).return_value

        async def mock_pop_tasks():
            return [returned_task]

        mock_task_source.pop_tasks = mock_pop_tasks
        return mock_task_source

    fake_task = {'task': 'task'}
    task_source = mock_task_source(returned_task=fake_task)
    task_poller = TaskPoller(task_source)

    handled_tasks = queue.Queue()

    async def add_to_handled_and_cancel_polling(item):
        handled_tasks.put(item)
        polling_task.cancel()

    loop = asyncio.get_event_loop()
    polling_task = loop.create_task(task_poller.poll(handle_task=add_to_handled_and_cancel_polling))

    try:
        await polling_task  # Run until cancelled
        assert False  # Should not get here
    except concurrent.futures.CancelledError:
        pass  # Should get here as polling was canceled

    assert not handled_tasks.empty()
    handled_item = handled_tasks.get()
    assert handled_item == fake_task
