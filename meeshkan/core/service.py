import asyncio
import concurrent.futures
from functools import partial
import logging
import os
from typing import List
import socket  # To verify daemon
import time
import sys

import dill
import Pyro4  # For daemon management

from .logger import remove_non_file_handlers

LOGGER = logging.getLogger(__name__)
DAEMON_BOOT_WAIT_TIME = 0.5  # In seconds


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class Service(object):
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

    def daemonize(self, build_api_bytes):
        """Makes sure the daemon runs even if the process that called `start_scheduler` terminates"""
        pid = os.fork()
        if pid > 0:  # Close parent process
            return
        remove_non_file_handlers()
        os.setsid()  # Separate from tty
        build_api = dill.loads(build_api_bytes)
        Pyro4.config.SERIALIZER = 'dill'
        Pyro4.config.SERIALIZERS_ACCEPTED.add('dill')
        Pyro4.config.SERIALIZERS_ACCEPTED.add('json')
        with build_api(self) as api, Pyro4.Daemon(host=self.host, port=self.port) as daemon:
            daemon.register(api, Service.OBJ_NAME)  # Register the API with the daemon

            async def start_daemon_and_polling_loops():
                polling_coro = api.poll()
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
            time.sleep(1.0)  # Allows data scraping

        return

    # Need single quotes here for type annotation, see
    # https://stackoverflow.com/questions/15853469/putting-current-class-as-return-type-annotation
    def start(self, mp_ctx, build_api_serialized) -> str:
        """
        Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess.
        :param mp_ctx: Multiprocessing context, e.g. `multiprocessing.get_context("spawn")`
        :param build_api_serialized: Dill-serialized function for creating API object
        :return: Pyro URI
        """

        if self.is_running():
            raise RuntimeError("Running already at {uri}".format(uri=self.uri))
        LOGGER.info("Starting service...")
        proc = mp_ctx.Process(target=self.daemonize, args=[build_api_serialized])
        self.terminate_daemon = mp_ctx.Event()
        proc.daemon = True
        proc.start()
        proc.join()
        time.sleep(DAEMON_BOOT_WAIT_TIME)  # Allow Pyro to boot up
        LOGGER.info("Service started.")
        return self.uri

    def stop(self) -> bool:
        if self.is_running():
            if not self.terminate_daemon:
                raise RuntimeError("Terminate daemon event does not exist.")
            self.terminate_daemon.set()  # Flag for requestLoop to terminate
            with Pyro4.Proxy(self.uri) as pyro_proxy:
                # triggers checking loopCondition
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
            return True
        return False
