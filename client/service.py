import errno
from multiprocessing import Process, Event  # For daemon initialization
import os
import ctypes
import psutil  # For verifying ports if Errno 98
import socket  # To verify daemon
import time
import Pyro4  # For daemon management

import client.scheduler
import client.api


DAEMON_BOOT_WAIT_TIME = 0.5  # In seconds

class Service(object):
    """
    Service for running the Python daemon
    """
    OBJ_NAME = "Meeshkan.scheduler"
    def __init__(self, port: int=7779):
        self.port = port
        self.host = socket.gethostname()
        self.terminate_daemon = Event()

    def is_running(self) -> bool:
        """Checks whether the daemon is running on localhost.
        Assumes the port is either taken by Pyro or is free.
        Offered as an alternative as `is_running2` requires `sudo` on MacOS systems.
        """
        with Pyro4.Proxy(self.uri) as p:
            try:
                p._pyroBind()
                return True
            except Pyro4.errors.CommunicationError:
                return False

    @property
    def uri(self):
        return f"PYRO:{Service.OBJ_NAME}@{self.host}:{self.port}"

    def start(self) -> str:
        """Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess."""
        def daemonize():
            """Makes sure the daemon runs even if the process that called `start_scheduler` terminates"""
            pid = os.fork()
            if pid > 0:  # Close parent process
                return
            os.setsid()  # Separate from tty
            daemon = Pyro4.Daemon(host=self.host, port=self.port)  # Save daemon so we can cleanly shutdown later on
            api = client.api.Api(scheduler=client.scheduler.Scheduler(), service=self)  # Initialize the API
            daemon.register(api, Service.OBJ_NAME)  # Register the API with the daemon
            daemon.requestLoop(lambda: not self.terminate_daemon.is_set())  # Loop until the event is set
            time.sleep(0.2)  # Allows data scraping
            daemon.close()  # Cleanup
            return

        is_running = self.is_running()
        if is_running:
            raise RuntimeError(f"Running already at {self.uri}")
        p = Process(target=daemonize)
        p.daemon = True
        p.start()
        time.sleep(DAEMON_BOOT_WAIT_TIME)  # Allow Pyro to boot up
        return self.uri

    def stop(self):
        if self.is_running():
            self.terminate_daemon.set()  # Flag for requestLoop to terminate
            with Pyro4.Proxy(self.uri) as p:
                p._pyroBind()  # triggers checking loopCondition
            self.terminate_daemon.clear()  # Clear the flag
            return True
        return False