"""
Code related to tasks invoked by the cloud.
"""
import asyncio
from enum import Enum
import logging
from typing import Callable, List
from uuid import UUID

LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class TaskType(Enum):
    StopJobTask = 0
    CreateGitJobTask = 1


class Task:
    def __init__(self, task_type: TaskType, **kwargs):
        self.type = task_type
        for key, value in kwargs:  # Add all keyword arguments as values
            setattr(self, key, value)

    def __getattr__(self, item):  # Don't raise any warnings for missing items, instead return None.
        return getattr(self, item, None)


class TaskFactory:
    @staticmethod
    def build(json_task):
        task_type = TaskType[json_task['__typename']]
        return Task(task_type=task_type, **{"job_id": UUID(json_task['job']['id'])})


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
