import asyncio
import concurrent.futures
import queue

import pytest

from meeshkan.tasks import Task, TaskType, TaskPoller


@pytest.mark.asyncio
async def test_task_poller_handles_tasks():

    fake_task = Task(job_id='id', task_type=TaskType.StopJobTask)

    def pop_tasks():
        return [fake_task]

    task_poller = TaskPoller(pop_tasks=pop_tasks)

    handled_tasks = queue.Queue()

    n_handled_tasks = 0

    async def add_to_handled_and_cancel_polling(item):
        handled_tasks.put(item)

        nonlocal n_handled_tasks
        n_handled_tasks += 1

        # Cancel polling after two handled tasks
        if n_handled_tasks == 2:
            polling_task.cancel()

    loop = asyncio.get_event_loop()
    polling_task = loop.create_task(task_poller.poll(handle_task=add_to_handled_and_cancel_polling, delay=0.1))

    try:
        await polling_task  # Run until cancelled
        assert False  # Should not get here
    except concurrent.futures.CancelledError:
        pass  # Should get here as polling was canceled
    finally:
        loop.close()

    # First handled item
    assert not handled_tasks.empty()
    handled_item = handled_tasks.get()
    assert handled_item.job_id == fake_task.job_id

    # Second handled item
    assert not handled_tasks.empty()
    handled_item = handled_tasks.get()
    assert handled_item.job_id == fake_task.job_id
