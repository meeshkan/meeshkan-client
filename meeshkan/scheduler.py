import logging
import queue
import threading
from typing import List, Tuple, Callable  # For self-documenting typing
import uuid

import meeshkan.job  # Defines scheduler jobs
import meeshkan.notifiers


LOGGER = logging.getLogger(__name__)


# Worker thread reading from queue and waiting for processes to finish
def read_queue(queue_: queue.Queue, do_work, stop_event: threading.Event) -> None:
    """
    Read and handle tasks from queue `q` until (1) queue item is None or (2) stop_event is set. Note that
    the currently running job is not forced to cancel: that should be done from another thread, letting queue reader
    to check loop condition.
    :param queue_: Synchronized queue
    :param do_work: Callback called with queue item as argument
    :param stop_event: Threading event signaling stop
    :return:
    """
    while not stop_event.is_set():
        item = queue_.get(block=True)
        if item is None or stop_event.is_set():
            break
        do_work(item)
        queue_.task_done()


class Scheduler(object):
    def __init__(self):
        self.submitted_jobs = []
        self._task_queue = queue.Queue()
        self._stop_thread_event = threading.Event()
        kwargs = {'q': self._task_queue, 'do_work': self._handle_job, 'stop_event': self._stop_thread_event}
        self._queue_reader = threading.Thread(target=read_queue, kwargs=kwargs)
        self._listeners: List[meeshkan.notifiers.Notifier] = []
        self._njobs = 0
        self._is_running = True
        self._running_job = None
        self._notification_status = dict()

    # Properties and Python magic

    @property
    def jobs(self):  # Needed to access internal list of jobs as object parameters are unexposable, only methods
        return self.submitted_jobs

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    # Notifaction related methods

    def get_notification_status(self, job_id: str):
        return self._notification_status[job_id]

    def register_listener(self, listener: meeshkan.notifiers.Notifier):
        self._listeners.append(listener)

    def notify_listeners(self, job: meeshkan.job.Job, message: str = None) -> bool:
        return self._internal_notifier_loop(job, lambda notifier: notifier.notify(job, message))

    def notify_listeners_job_start(self, job: meeshkan.job.Job) -> bool:
        return self._internal_notifier_loop(job, lambda notifier: notifier.notify_job_start(job))

    def notify_listeners_job_end(self, job: meeshkan.job.Job) -> bool:
        return self._internal_notifier_loop(job, lambda notifier: notifier.notify_job_end(job))

    def _internal_notifier_loop(self, job: meeshkan.job.Job,
                                notify_method: Callable[[meeshkan.notifiers.Notifier], None]) -> bool:
        status = True
        for notifier in self._listeners:
            try:
                notify_method(notifier)
                self._notification_status[job.id] = "Success"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Notifier %s failed", notifier.__class__.__name__)
                self._notification_status[job.id] = "Failed"
                status = False
        return status

    # Job handling methods

    def _handle_job(self, job: meeshkan.job.Job) -> None:
        LOGGER.debug("Handling job: %s", job)
        if job.stale:
            return

        try:
            self.notify_listeners_job_start(job)
            self._running_job = job
            job.launch_and_wait()
            self._running_job = None
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Running job failed")

        self.notify_listeners_job_end(job)
        LOGGER.debug("Finished handling job: %s", job)

    def create_job(self, args: Tuple[str, ...], name: str = None):
        job_number = self._njobs
        job_uuid = uuid.uuid4()
        output_path = meeshkan.config.JOBS_DIR.joinpath(str(job_uuid))
        executable = meeshkan.job.ProcessExecutable(args, output_path=output_path)
        self._njobs += 1
        return meeshkan.job.Job(executable, job_number=job_number, job_uuid=job_uuid, name=name or f"Job #{job_number}")

    def submit_job(self, job: meeshkan.job.Job):
        job.status = meeshkan.job.JobStatus.QUEUED
        self._notification_status[job.id] = "NA"
        self._task_queue.put(job)  # TODO Blocks if queue full
        self.submitted_jobs.append(job)
        LOGGER.debug("Job submitted: %s", job)

    def stop_job(self, job_id: int):
        jobs_with_id: List[meeshkan.job.Job] = [job for job in self.jobs if job.id == job_id]
        if not jobs_with_id:
            return
        job = jobs_with_id[0]
        job.cancel()

    # Scheduler service methods

    def start(self):
        if not self._queue_reader.is_alive():
            self._queue_reader.start()

    def stop(self):
        # TODO Terminate the process currently running with --force?
        if self._is_running:
            self._task_queue.put(None)  # Signal exit if thread is blocking
            self._stop_thread_event.set()  # Signal exit to worker thread, required as "None" may not be next task
            self._is_running = False
            if self._running_job is not None:
                self._running_job.cancel()
            if self._queue_reader.ident is not None:
                # Wait for the thread to finish
                self._queue_reader.join()
