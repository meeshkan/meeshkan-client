import asyncio
import concurrent.futures
from functools import partial
import logging
import multiprocessing
import os
from typing import List
import socket  # To verify daemon
import time
import sys

import dill
import Pyro4  # For daemon management

from .logger import remove_non_file_handlers
from ..__build__ import _build_api

LOGGER = logging.getLogger(__name__)
DAEMON_BOOT_WAIT_TIME = 2.0  # In seconds


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class Service:
    """
    Service for running the Python daemon
    """
    OBJ_NAME = "Meeshkan.scheduler"

    def __init__(self, port: int = 7779):
        self.port = port
        self.host = Service._get_localhost()
        self.terminate_daemon = None  # Set at start time

    @staticmethod
    def _get_localhost():
        if sys.platform.startswith('darwin'):
            # Mac OS has issues with `socket.gethostname()`
            # See https://bugs.python.org/issue29705 and https://bugs.python.org/issue35164
            return socket.gethostbyname("localhost")  # Assume localhost defined in `hosts`
        return socket.gethostname()

    def is_running(self) -> bool:
        """Checks whether the daemon is running on localhost.
        Assumes the port is either taken by Pyro or is free.
        Offered as an alternative as `is_running2` requires `sudo` on MacOS systems.
        """
        with Pyro4.Proxy(self.uri) as pyro_proxy:
            try:
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
                return True
            except Pyro4.errors.CommunicationError:
                return False

    @property
    def api(self) -> Pyro4.Proxy:
        return Pyro4.Proxy(self.uri)

    @property
    def uri(self):
        return "PYRO:{obj_name}@{host}:{port}".format(obj_name=Service.OBJ_NAME, host=self.host, port=self.port)

    def daemonize(self, serialized):
        """Makes sure the daemon runs even if the process that called `start_scheduler` terminates"""
        pid = os.fork()
        if pid > 0:  # Close parent process
            return
        if not self.terminate_daemon:
            self.terminate_daemon = multiprocessing.get_context("spawn").Event()
        remove_non_file_handlers()
        os.setsid()  # Separate from tty
        cloud_client = dill.loads(serialized.encode('cp437'))
        Pyro4.config.SERIALIZER = 'dill'
        Pyro4.config.SERIALIZERS_ACCEPTED.add('dill')
        Pyro4.config.SERIALIZERS_ACCEPTED.add('json')
        with _build_api(self, cloud_client=cloud_client) as api, Pyro4.Daemon(host=self.host, port=self.port) as daemon:
            daemon.register(api, Service.OBJ_NAME)  # Register the API with the daemon

            async def start_daemon_and_polling_loops():
                polling_coro = api.poll()  # pylint: disable=assignment-from-no-return
                # Create task from polling coroutine and schedule for execution
                # Note: Unlike `asyncio.create_task`, `loop.create_task` works in Python < 3.7
                polling_task = loop.create_task(polling_coro)  # type: asyncio.Task

                # Run the blocking Pyro daemon request loop in a dedicated thread and `await` until finished
                # (`terminate_daemon` event set)
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    try:
                        loop_daemon_until_event_set = partial(daemon.requestLoop,
                                                              lambda: not self.terminate_daemon.is_set())
                        await loop.run_in_executor(pool, loop_daemon_until_event_set)
                    finally:
                        LOGGER.debug("Canceling polling task.")
                        polling_task.cancel()

            loop = asyncio.get_event_loop()
            try:
                # Run event loop until request loops finished
                loop.run_until_complete(start_daemon_and_polling_loops())
            finally:
                loop.close()
            LOGGER.debug("Exiting service.")
            time.sleep(2.0)  # Allows data scraping

        return

    def start(self, mp_ctx, cloud_client_serialized: str) -> str:
        """
        Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess.
        :param mp_ctx: Multiprocessing context, e.g. `multiprocessing.get_context("spawn")`
        :param cloud_client_serialized: Dill-serialized CloudClient instance
        :return: Pyro URI
        """

        if self.is_running():
            raise RuntimeError("Running already at {uri}".format(uri=self.uri))
        LOGGER.info("Starting service...")
        proc = mp_ctx.Process(target=self.daemonize, args=[cloud_client_serialized])
        proc.daemon = True
        proc.start()
        proc.join()
        time.sleep(DAEMON_BOOT_WAIT_TIME)  # Allow Pyro to boot up
        LOGGER.info("Service started.")
        return self.uri

    def stop(self) -> bool:
        if self.is_running():
            if not self.terminate_daemon:
                raise RuntimeError("Terminate daemon event does not exist. "
                                   "The stop() method may have called from the wrong process.")
            self.terminate_daemon.set()  # Flag for requestLoop to terminate
            with Pyro4.Proxy(self.uri) as pyro_proxy:
                # triggers checking loopCondition
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
            return True
        return False
