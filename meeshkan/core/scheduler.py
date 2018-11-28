import logging
import queue
import threading
from typing import Any, Dict, List, Tuple, Callable, Optional, Union  # For self-documenting typing
from pathlib import Path
import uuid
import os
import asyncio

from .tracker import TrackingPoller, TrackerBase
from .job import ProcessExecutable, JobStatus, Job
from .config import JOBS_DIR
from ..exceptions import JobNotFoundException
from ..notifications.notifiers import Notifier

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


LOGGER = logging.getLogger(__name__)


class QueueProcessor:
    """
    Process items from queue in a new thread. Usage:
    1) queue_processor.start(queue_=..., process_item=...)
    2) queue_processor.schedule_stop()
    3) queue_processor.wait_stop()
    The two shutdown steps ensure that the caller can cancel the currently running task between them,
    ensuring that processor exits without processing new jobs.
    """
    def __init__(self):
        self._stop_event = threading.Event()
        self._queue = None
        self._thread = None

    def start(self, queue_, process_item):
        """
        Read and handle tasks from queue `queue_` until (1) queue item is None or (2) stop_event is set. Note that
        the currently running job is not forced to cancel: that should be done from another thread, letting queue reader
        to check loop condition. `QueueProcessor` is NOT safe for reuse for processing other queues.
        :param queue_: Synchronized queue
        :param process_item: Callback called with queue item as argument
        :return:
            """
        self._queue = queue_
        self._thread = threading.Thread(target=self.__process, args=(process_item,))
        self._stop_event.clear()
        self._thread.start()

    def __process(self, process_item):
        if not self.is_running():
            raise RuntimeError("QueueProcessor must be started first.")
        while not self._stop_event.is_set():
            item = self._queue.get(block=True)
            if item is None or self._stop_event.is_set():
                break
            process_item(item)
            self._queue.task_done()

    def schedule_stop(self):
        if not self.is_running():
            return
        self._stop_event.set()  # Signal exit to worker thread, required as "None" may not be next task
        self._queue.put(None, block=False)  # Signal exit if thread is blocking

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def wait_stop(self):
        if self.is_running():
            self._thread.join()
            self._thread = None
            self._queue = None


class Scheduler(object):
    def __init__(self, queue_processor: QueueProcessor, notifier: Notifier = None):
        self._queue_processor = queue_processor
        self.submitted_jobs = dict()  # type: Dict[uuid.UUID, Job]
        self._task_queue = queue.Queue()  # type: queue.Queue
        self._running_job = None  # type: Optional[Job]
        self._history_by_job = dict()  # type: Dict[uuid.UUID, TrackerBase]  # TODO: Refactor into Job/TrackingPoller?
        self._job_poller = TrackingPoller(self.__query_and_report)
        self._event_loop = asyncio.get_event_loop()  # Save the event loop for out-of-thread operations
        self._notifier = notifier  # type: Optional[Notifier]

    # Properties and Python magic

    @property
    def jobs(self):  # Needed to access internal list of jobs as object parameters are unexposable, only methods
        return list(self.submitted_jobs.values())

    @property
    def is_running(self):
        return self._queue_processor.is_running()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    # Job handling methods

    def _handle_job(self, job: Job) -> None:
        LOGGER.debug("Handling job: %s", job)
        if job.stale:
            return

        self._running_job = job
        # Create and schedule a task from the Polling job, so we can cancel it without killing the event loop
        task = self._event_loop.create_task(self._job_poller.poll(job))  # type: asyncio.Task
        if self._notifier:
            self._notifier.notify_job_start(job)
        try:
            job.launch_and_wait()
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Running job failed")
        finally:
            task.cancel()

        if self._notifier:
            self._notifier.notify_job_end(job)
        self._running_job = None
        LOGGER.debug("Finished handling job: %s", job)

    @staticmethod
    def _verify_python_executable(args: Tuple[str, ...]):
        """Simply checks if the first argument's extension is .py, and if so, prepends 'python' to args"""
        if len(args) > 0:    # pylint: disable=len-as-condition
            if os.path.splitext(args[0])[1] == ".py":
                args = ("python",) + args
        return args

    def create_job(self, args: Tuple[str, ...], name: str = None, poll_interval: int = None):
        job_number = len(self.jobs)
        job_uuid = uuid.uuid4()
        args = self._verify_python_executable(args)
        LOGGER.debug("Creating job for %s", args)
        output_path = JOBS_DIR.joinpath(str(job_uuid))
        executable = ProcessExecutable(args, output_path=output_path)
        job_name = name or "Job #{job_number}".format(job_number=job_number)
        return Job(executable, job_number=job_number, job_uuid=job_uuid, name=job_name, poll_interval=poll_interval)

    def submit_job(self, job: Job):
        job.status = JobStatus.QUEUED
        self._history_by_job[job.id] = TrackerBase()
        self.submitted_jobs[job.id] = job
        self._task_queue.put(job)  # TODO Blocks if queue full
        LOGGER.debug("Job submitted: %s", job)

    def stop_job(self, job_id: uuid.UUID):
        if job_id not in self.submitted_jobs:
            LOGGER.debug("Ignoring stopping unknown job with ID: %s", str(job_id))
            return
        self.submitted_jobs[job_id].cancel()

    # Tracking methods

    def report_scalar(self, pid, name, val):
        # Find the right job id
        job_id = [job.id for job in self.jobs if job.pid == pid]
        if len(job_id) != 1:
            raise JobNotFoundException(job_id=str(pid))
        job_id = job_id[0]
        self._history_by_job[job_id].add_tracked(val_name=name, value=val)
        LOGGER.debug("Logged scalar %s with new value %s", name, val)

    def query_scalars(self, job_id, name: str = "", latest_only: bool = True, plot: bool = False):
        return self._history_by_job[job_id].get_updates(name=name, plot=plot, latest=latest_only)

    def __query_and_report(self, job_id: uuid.UUID):
        if self._notifier:
            # Get updates; TODO - vals should be reported once we update schema...
            # pylint: disable=unused-variable
            vals, imgpath = self.query_scalars(job_id, latest_only=True, plot=True)
            if vals and imgpath is not None:  # Only send updates if there exists any updates and a valid imgpath
                self._notifier.notify(self.submitted_jobs[job_id], imgpath, n_iterations=-1)
                os.remove(imgpath)

    # Scheduler service methods

    def start(self):
        if not self._queue_processor.is_running():
            LOGGER.debug("Start queue processor")
            self._queue_processor.start(queue_=self._task_queue, process_item=self._handle_job)
            LOGGER.debug("Queue processor started")

    def stop(self):
        # self._job_poller.stop()
        self._queue_processor.schedule_stop()
        if self._running_job is not None:
            # TODO Add an option to not cancel the currently running job?
            self._running_job.cancel()
        if self._queue_processor.is_running():
            # Wait for the thread to finish
            self._queue_processor.wait_stop()
