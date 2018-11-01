import errno
from multiprocessing import Process  # For daemon initialization
import os
import psutil  # For verifying ports if Errno 98
import socket  # To verify daemon
import time

import Pyro4  # For daemon management

from client.scheduler import Scheduler
from client.api import Api


class Service(object):
    """
    Service for running the Python daemon
    """

    def __init__(self, port: int=7779):
        self.port = port
        self.host = socket.gethostname()
        self.obj_name = "Meeshkan.scheduler"

    def is_running(self):
        with Pyro4.Proxy(self.uri) as p:
            try:
                p._pyroBind()
                return True
            except Pyro4.errors.CommunicationError:
                return False

    def is_running2(self):
        """Checks whether the daemon is running on localhost
            :return:
                -1 if the daemon isn't running
                None if something is running on the specified port but we're unable to verify the PID
                True if daemon is running
                False if something else is running on the port
        """
        connections = psutil.net_connections()
        pid = -1
        for conn in connections:
            if conn.fd != -1:  # Only consider valid connections
                if conn.laddr.port == self.port:  # Check laddr
                    pid = conn.pid
                    break
        if pid == -1 or pid is None:
            return pid
        # Verify process via PID
        proc_name = psutil.Process(pid).name()  # assume python processes are our own...
        return 'python' in proc_name

    @property
    def uri(self):
        return f"PYRO:{self.obj_name}@{self.host}:{self.port}"

    def start(self):
        """Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess."""

        obj_name = "Meeshkan.scheduler"

        def daemonize():  # Makes sure the daemon runs even if the process that called `start_scheduler` terminates
            pid = os.fork()
            if pid > 0:  # Close parent process
                return
            os.setsid()
            daemon = Pyro4.Daemon(host=self.host, port=self.port)
            api = Api(scheduler=Scheduler(daemon), host=self.host, port=self.port)
            Pyro4.Daemon.serveSimple({api: obj_name}, ns=False, daemon=daemon, verbose=False)
            return

        # daemon_status = self.is_running()
        is_running = self.is_running()

        if is_running:
            raise RuntimeError(f"Running already at {self.uri}")
        p = Process(target=daemonize)
        p.daemon = True
        p.start()
        time.sleep(1)  # Allow Pyro to boot up
        # elif daemon_status is False:
         #   raise OSError(errno.EADDRINUSE)  # host:port is not free and is not python process
        # daemon_status is either True (daemon is running) or None, in which case we assume the process is ours.
        return self.uri  # URI
