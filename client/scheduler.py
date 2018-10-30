import queue
import threading
import time
from multiprocessing import Process  # For daemon initialization
import os  # Ditto (for daemonizing the Pyro4 process)
import errno
from typing import Callable  # For self-documenting typing
import Pyro4  # For daemon management
import psutil  # For verifying ports if Errno 98
import socket  # To verify daemon
from .job import Job  # Defines scheduler jobs

# Worker thread reading from queue and waiting for processes to finish
def read_queue(q: queue.Queue, do_work, stop_event: threading.Event) -> None:
    while True:
        if stop_event.is_set():
            return
        if q.empty():
            time.sleep(1)
        else:
            item = q.get()
            do_work(item)
            q.task_done()

@Pyro4.expose
@Pyro4.behavior(instance_mode="single")  # Singleton
class Scheduler(object):
    def __init__(self, daemon):
        self.submitted_jobs = []
        self._task_queue = queue.Queue()
        self._stop_thread_event = threading.Event()
        kwargs = {'q': self._task_queue, 'do_work': self._handle_job, 'stop_event': self._stop_thread_event}
        self._queue_reader = threading.Thread(target=read_queue, kwargs=kwargs)
        self._listeners = []
        self._njobs = 0
        self._is_running = True
        self._running_job = None
        self.daemon = daemon

    @property
    def jobs(self):  # Needed to access internal list of jobs as object parameters are unexposable, only methods
        return self.submitted_jobs

    def __enter__(self):
        self._queue_reader.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def register_listener(self, listener: Callable[[Job, int], None]):
        self._listeners.append(listener)

    def _handle_job(self, job: Job) -> None:
        if not job.stale:
            print("%s: launching job: %s" % (threading.current_thread().name, job))
            try:
                self._running_job = job
                return_code = job.launch_and_wait()
                self._running_job = None
                for notify in self._listeners:
                    notify(job, return_code)
            except Exception as e:
                print("Job failed: %s" % job)  # TODO Notify failure
        else:
            print('Skipping stale job %d' % job.id)

    def get_id(self):
        return self._njobs

    def submit_job(self, job: Job):
        self._njobs += 1
        self._task_queue.put(job)  # TODO Blocks if queue full
        self.submitted_jobs.append(job)

    def stop_job(self, job_id: int):
        jobs_with_id = [job for job in self.jobs if job.id == job_id]
        if len(jobs_with_id) == 0:
            print('No matching job with id %d found' % job_id)
            return
        job = jobs_with_id[0]
        job.cancel()

    def list_jobs(self):
        print('---Jobs---')
        for job in self.jobs:
            print(job)
        print('----------')

    def stop(self):
        # TODO Terminate the process currently running
        if self._is_running:
            print('Telling the worker to stop after processing...')
            self._stop_thread_event.set()  # Signal exit to worker thread
            self._is_running = False
            if self._running_job is not None:
                self._running_job.cancel()
            # Wait for the thread to finish
            self._queue_reader.join()

    def terminate_daemon(self, host, port):
        # Kill process ran as daemon # TODO - should this be part of stop method?
        self.daemon.shutdown()


def is_daemon_running(port: int =7779):
    """Checks whether the daemon is running on localhost
    :return:
        -1 if the daemon isn't running
        None if something is running on the specified port but we're unable to verify the PID
        True if daemon is running
        False if something else is running on the port
    """
    # Assume daemon is running and look for it; find the PID that uses this port
    connections = psutil.net_connections()
    pid = -1
    for conn in connections:
        if conn.fd != -1:  # Only consider valid connections
            if conn.laddr.port == port:  # Check laddr
                pid = conn.pid
                break
    if pid == -1 or pid is None:
        return pid
    # Verify process via PID
    proc_name = psutil.Process(pid).name()    # assume python processes are our own...
    return 'python' in proc_name

def start_scheduler(host: str ='127.0.0.1', port: int =7779):
    """Runs the scheduler as a Pyro4 object on a predetermined location in a subprocess."""
    obj_name = "Meeshkan.scheduler"
    def daemonize():  # Makes sure the daemon runs even if the process that called `start_scheduler` terminates
        pid = os.fork()
        if pid > 0:  # Close parent process
            return
        os.setsid()
        daemon = Pyro4.Daemon(host=host, port=port)
        Pyro4.Daemon.serveSimple({Scheduler(daemon): obj_name}, ns=False, daemon=daemon, verbose=False)
        return

    daemon_status = is_daemon_running(port)
    if daemon_status == -1:    # host:port is free, boot up the scheduler/daemon
        p = Process(target=daemonize)
        p.daemon = True
        p.start()
        time.sleep(1)  # Allow Pyro to boot up
    elif daemon_status is False:
        raise OSError(errno.EADDRINUSE)  # host:port is not free and is not python process
    # daemon_status is either True (daemon is running) or None, in which case we assume the process is ours.
    return f"PYRO:{obj_name}@{host}:{port}"  # URI