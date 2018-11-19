"""
Code related to tasks invoked by the cloud.
"""
import asyncio
from enum import Enum
import logging
from typing import Callable, List


LOGGER = logging.getLogger(__name__)


class TaskType(Enum):
    StopJobTask = 0


class Task:
    def __init__(self, job_id, task_type: TaskType):
        self.job_id = job_id
        self.type = task_type


class TaskPoller:
    def __init__(self, pop_tasks: Callable[[], List[Task]]):
        """
        Polls new tasks from the server.
        :param pop_tasks: Asynchronous method for fetching new tasks
        """
        self._pop_tasks = pop_tasks

    async def poll(self, handle_task, delay=10):
        """
        Polling for tasks.
        :param handle_task: Async task handler. Must NOT block the event loop.
        :param delay: Time in seconds to wait between requesting new tasks. Should be reasonably long to avoid
        bombarding the server.
        :return:
        """
        loop = asyncio.get_event_loop()
        try:
            while True:
                try:
                    tasks = await loop.run_in_executor(None, self._pop_tasks)  # type: List[Task]
                    for task in tasks:
                        await handle_task(task)
                except Exception as ex:  # pylint:disable=broad-except
                    if isinstance(ex, asyncio.CancelledError):
                        raise
                    LOGGER.exception("Failed fetching or handling new tasks.")
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            LOGGER.debug("Polling canceled.")
            raise
