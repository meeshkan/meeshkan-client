import asyncio
import concurrent.futures
import queue

import pytest

from meeshkan.tasks import Task, TaskPoller


@pytest.mark.asyncio
async def test_task_poller_handles_tasks():

    fake_task = Task(job_id='id', task='STOP')

    async def pop_tasks():
        return [fake_task]

    task_poller = TaskPoller(build_pop_tasks_coro=pop_tasks)

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
    assert handled_item.job_id == fake_task.job_id
