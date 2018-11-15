import asyncio
import concurrent.futures
from functools import partial
import logging
from multiprocessing import Process, Event  # For daemon initialization
import os
from typing import Any, Callable
import socket  # To verify daemon
import time
import sys

import Pyro4  # For daemon management

import meeshkan.logger

LOGGER = logging.getLogger(__name__)
DAEMON_BOOT_WAIT_TIME = 0.5  # In seconds


class Service(object):
    """
    Service for running the Python daemon
    """
    OBJ_NAME = "Meeshkan.scheduler"

    def __init__(self, port: int = 7779):
        self.port = port
        self.host = Service._get_localhost()
        self.terminate_daemon = Event()

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

    # Need single quotes here for type annotation, see
    # https://stackoverflow.com/questions/15853469/putting-current-class-as-return-type-annotation
    def start(self, build_api: Callable[['Service'], Any]) -> str:
        """Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess."""
        def daemonize():
            """Makes sure the daemon runs even if the process that called `start_scheduler` terminates"""
            pid = os.fork()
            if pid > 0:  # Close parent process
                return
            meeshkan.logger.remove_non_file_handlers()
            os.setsid()  # Separate from tty
            with build_api(self) as api, Pyro4.Daemon(host=self.host, port=self.port) as daemon:
                daemon.register(api, Service.OBJ_NAME)  # Register the API with the daemon

                async def start_daemon_and_polling_loops():
                    loop_ = asyncio.get_event_loop()

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
                            await loop_.run_in_executor(pool, loop_daemon_until_event_set)
                        finally:
                            LOGGER.debug("Canceling polling task.")
                            polling_task.cancel()

                loop = asyncio.get_event_loop()
                loop.run_until_complete(start_daemon_and_polling_loops())  # Run event loop until request loops finished
                LOGGER.debug("Exiting service.")
                time.sleep(0.2)  # Allows data scraping

            return

        if self.is_running():
            raise RuntimeError("Running already at {uri}".format(uri=self.uri))
        LOGGER.info("Starting service...")
        proc = Process(target=daemonize)
        proc.daemon = True
        proc.start()
        time.sleep(DAEMON_BOOT_WAIT_TIME)  # Allow Pyro to boot up
        LOGGER.info("Service started.")
        return self.uri

    def stop(self) -> bool:
        if self.is_running():
            self.terminate_daemon.set()  # Flag for requestLoop to terminate
            with Pyro4.Proxy(self.uri) as pyro_proxy:
                # triggers checking loopCondition
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
            self.terminate_daemon.clear()  # Clear the flag
            return True
        return False
