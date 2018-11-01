import queue
import threading
import time
from typing import Callable  # For self-documenting typing
from client.job import Job  # Defines scheduler jobs


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
    def __init__(self, daemon=None):
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

    def terminate_daemon(self):
        # Kill process ran as daemon # TODO - should this be part of stop method?
        if self.daemon is not None:
            self.daemon.shutdown()
