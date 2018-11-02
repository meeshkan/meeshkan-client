import logging
import queue
import threading
import time
from typing import List  # For self-documenting typing

import client.job  # Defines scheduler jobs
import client.notifiers


LOGGER = logging.getLogger(__name__)


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


class Scheduler(object):
    def __init__(self):
        self.submitted_jobs = []
        self._task_queue = queue.Queue()
        self._stop_thread_event = threading.Event()
        kwargs = {'q': self._task_queue, 'do_work': self._handle_job, 'stop_event': self._stop_thread_event}
        self._queue_reader = threading.Thread(target=read_queue, kwargs=kwargs)
        self._listeners: List[client.notifiers.Notifier] = []
        self._njobs = 0
        self._is_running = True
        self._running_job = None

    @property
    def jobs(self):  # Needed to access internal list of jobs as object parameters are unexposable, only methods
        return self.submitted_jobs

    def start(self):
        if not self._queue_reader.is_alive():
            self._queue_reader.start()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def register_listener(self, listener: client.notifiers.Notifier):
        self._listeners.append(listener)

    def _handle_job(self, job: client.job.Job) -> None:
        LOGGER.debug("Handling job: %s", job)
        if job.stale:
            return

        try:
            self._running_job = job
            job.launch_and_wait()
            self._running_job = None
        except:
            LOGGER.exception("Running job failed")

        for notifier in self._listeners:
            try:
                notifier.notify(job)
            except:
                LOGGER.exception("Notifier failed")

        LOGGER.debug("Finished handling job: %s", job)

    def get_number(self):
        return self._njobs

    def submit_job(self, job: client.job.Job):
        self._njobs += 1
        job.status = client.job.JobStatus.QUEUED
        self._task_queue.put(job)  # TODO Blocks if queue full
        self.submitted_jobs.append(job)
        LOGGER.debug("Job submitted: %s", job)

    def stop_job(self, job_id: int):
        jobs_with_id: List[client.job.Job] = [job for job in self.jobs if job.id == job_id]
        if not jobs_with_id:
            return
        job = jobs_with_id[0]
        job.cancel()

    def stop(self):
        # TODO Terminate the process currently running
        if self._is_running:
            self._stop_thread_event.set()  # Signal exit to worker thread
            self._is_running = False
            if self._running_job is not None:
                self._running_job.cancel()
            if self._queue_reader.ident is not None:
                # Wait for the thread to finish
                self._queue_reader.join()
