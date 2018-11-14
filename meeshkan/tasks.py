"""
Code related to tasks invoked by the cloud.
"""
import asyncio
import logging
from typing import Awaitable, Callable, List


LOGGER = logging.getLogger(__name__)


class Task:
    def __init__(self, job_id, task):
        self.job_id = job_id
        self.task = task


class TaskPoller:
    def __init__(self, build_pop_tasks_coro: Callable[[], Awaitable[List[Task]]]):
        """
        Polls new tasks from the server.
        :param pop_tasks: Asynchronous method for fetching new tasks
        """
        self._build_pop_tasks_coro = build_pop_tasks_coro

    async def poll(self, handle_task, delay=10):
        """
        Polling for tasks.
        :param handle_task: Async task handler. Must NOT block the event loop.
        :param delay: Time in seconds to wait between requesting new tasks. Should be reasonably long to avoid
        bombarding the server.
        :return:
        """
        try:
            while True:
                try:
                    tasks = await self._build_pop_tasks_coro()  # type: List[Task]
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
