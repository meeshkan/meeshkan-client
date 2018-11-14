"""
Code related to tasks invoked by the cloud.
"""
import asyncio
import logging
from typing import Callable

import requests

LOGGER = logging.getLogger(__name__)


class TaskSource:
    """
    Asynchronous task source. Usage as context manager:
    with task_source:                          # Builds session
        tasks = await task_source.pop_tasks()  # Closes session when exiting
    """
    def __init__(self, build_session: Callable[[], requests.Session] = requests.Session):
        self._build_session = build_session
        self._session = None

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        if self._session is not None:
            raise RuntimeError("Trying to start TaskSource twice before closing.")
        self._session = self._build_session()

    def close(self):
        if self._session is None:
            raise RuntimeError("Trying to close TaskSource without starting.")
        self._session.close()
        self._session = None

    async def pop_tasks(self):
        await asyncio.sleep(0.1)  # TODO: Query server
        return [{'counter': 0}]


class TaskPoller:
    def __init__(self, task_source):
        self._task_source = task_source

    async def poll(self, handle_task, delay=10):
        """
        Polling for tasks.
        :param handle_task: Async task handler. Must NOT block the event loop.
        :param delay: Time in seconds to wait between requesting new tasks. Should be reasonably long to avoid
        bombarding the server.
        :return:
        """
        try:
            with self._task_source:
                while True:
                    tasks = await self._task_source.pop_tasks()
                    for task in tasks:
                        await handle_task(task)
                    await asyncio.sleep(delay)
        except asyncio.CancelledError:
            LOGGER.debug("Polling canceled.")
            raise
