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

import Pyro4  # For daemon management

from .logger import remove_non_file_handlers
from ..__build__ import _build_api
from .serializer import Serializer
from ..exceptions import AgentNotAvailableException

LOGGER = logging.getLogger(__name__)
DAEMON_BOOT_WAIT_TIME = 2.0  # In seconds


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


def _platform_is_darwin() -> bool:
    return sys.platform.startswith('darwin')


def _get_localhost():
    if _platform_is_darwin():
        # Mac OS has issues with `socket.gethostname()`
        # See https://bugs.python.org/issue29705 and https://bugs.python.org/issue35164
        return socket.gethostbyname("localhost")  # Assume localhost defined in `hosts`
    return socket.gethostname()


class Service:
    """
    Service for running the Python daemon
    """
    OBJ_NAME = "Meeshkan.scheduler"
    PORT = 7779
    HOST = _get_localhost()
    MULTIPROCESSING_CONTEXT = multiprocessing.get_context("spawn")
    URI = "PYRO:{obj_name}@{host}:{port}".format(obj_name=OBJ_NAME,
                                                 host=HOST,
                                                 port=PORT)

    def __init__(self, terminate_daemon_event: asyncio.Event):
        self.terminate_daemon_event = terminate_daemon_event

    @staticmethod
    def is_running() -> bool:
        """Checks whether the daemon is running on localhost.
        Assumes the port is either taken by Pyro or is free.
        """
        with Service._pyro_proxy() as pyro_proxy:
            try:
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
                return True
            except Pyro4.errors.CommunicationError:
                return False

    @staticmethod
    def api() -> Pyro4.Proxy:
        """
        Get Pyro proxy for the agent API.

        :raises AgentNotAvailableException: If agent is not running.
        :return: Pyro proxy.
        """
        if not Service.is_running():
            raise AgentNotAvailableException()
        return Service._pyro_proxy()

    @staticmethod
    def _pyro_proxy():
        """
        Get Pyro proxy. Does not check proxy is available.

        :return: Pyro proxy.
        """
        return Pyro4.Proxy(Service.URI)

    @staticmethod
    def daemonize(cloud_client_serialized):
        """Makes sure the daemon runs even if the process that called `start` terminates"""
        pid = os.fork()
        if pid > 0:  # Close parent process
            return
        service = Service(terminate_daemon_event=asyncio.Event())
        remove_non_file_handlers()
        os.setsid()  # Separate from tty
        cloud_client = Serializer.deserialize(cloud_client_serialized)
        Pyro4.config.SERIALIZER = Serializer.NAME
        Pyro4.config.SERIALIZERS_ACCEPTED.add(Serializer.NAME)
        Pyro4.config.SERIALIZERS_ACCEPTED.add('json')
        with _build_api(service, cloud_client=cloud_client) as api,\
                Pyro4.Daemon(host=Service.HOST, port=Service.PORT) as daemon:
            api.register_with_pyro(daemon, name=Service.OBJ_NAME)  # Register the API with the daemon

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
                                                              lambda: not service.terminate_daemon_event.is_set())
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

    @staticmethod
    def start(cloud_client_serialized: str) -> str:
        """
        Runs the agent as a Pyro4 object on a predetermined location in a subprocess.
        :param cloud_client_serialized: Serialized CloudClient instance
        :raises RuntimeError: If Pyro server is already running
        :return: Pyro URI
        """

        if Service.is_running():
            raise RuntimeError("Running already at {uri}".format(uri=Service.URI))

        if _platform_is_darwin():
            # Temporary fix for fork safety issues in macOS
            # https://bugs.python.org/issue33725
            # https://github.com/ansible/ansible/issues/49207
            # http://sealiesoftware.com/blog/archive/2017/6/5/Objective-C_and_fork_in_macOS_1013.html
            os.putenv("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

        LOGGER.info("Starting service...")
        proc = Service.MULTIPROCESSING_CONTEXT.Process(
            target=Service.daemonize,
            args=[cloud_client_serialized])
        proc.daemon = True
        proc.start()
        proc.join()
        time.sleep(DAEMON_BOOT_WAIT_TIME)  # Allow Pyro to boot up
        LOGGER.info("Service started.")
        return Service.URI

    def stop(self) -> bool:
        if self.is_running():
            if self.terminate_daemon_event is None:
                raise RuntimeError("Terminate daemon event does not exist. "
                                   "The stop() method may have been called from the wrong process.")
            self.terminate_daemon_event.set()  # Flag for requestLoop to terminate
            with Service._pyro_proxy() as pyro_proxy:
                # triggers checking loopCondition
                pyro_proxy._pyroBind()  # pylint: disable=protected-access
            return True
        return False
