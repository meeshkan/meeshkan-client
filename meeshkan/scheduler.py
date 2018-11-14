import logging
import queue
import threading
from typing import Any, Dict, List, Tuple, Callable, Optional  # For self-documenting typing
import uuid

import meeshkan.job  # Defines scheduler jobs
import meeshkan.notifiers
import meeshkan.tasks


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
        self._queue.put(None)  # Signal exit if thread is blocking

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def wait_stop(self):
        if self.is_running():
            self._thread.join()
            self._thread = None
            self._queue = None


class Scheduler(object):
    def __init__(self, queue_processor: QueueProcessor, task_poller: meeshkan.tasks.TaskPoller):
        self._queue_processor = queue_processor
        self._task_poller = task_poller
        self.submitted_jobs = []  # type: List[meeshkan.job.Job]
        self._task_queue = queue.Queue()  # type: queue.Queue
        self._listeners = []  # type: List[meeshkan.notifiers.Notifier]
        self._njobs = 0
        self._is_running = True
        self._running_job = None  # type: Optional[meeshkan.job.Job]
        self._notification_status = dict()  # type: Dict[Any, str]

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
        except Exception:  # pylint:disable=broad-except
            LOGGER.exception("Running job failed")
        finally:
            self._running_job = None

        self.notify_listeners_job_end(job)
        LOGGER.debug("Finished handling job: %s", job)

    def create_job(self, args: Tuple[str, ...], name: str = None):
        job_number = self._njobs
        job_uuid = uuid.uuid4()
        output_path = meeshkan.config.JOBS_DIR.joinpath(str(job_uuid))
        executable = meeshkan.job.ProcessExecutable(args, output_path=output_path)
        self._njobs += 1
        return meeshkan.job.Job(executable, job_number=job_number, job_uuid=job_uuid,
                                name=name or "Job #{job_number}".format(job_number=job_number))

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
        if not self._queue_processor.is_running():
            LOGGER.debug("Start queue processor")
            self._queue_processor.start(queue_=self._task_queue, process_item=self._handle_job)
            LOGGER.debug("Queue processor started")

    def stop(self):
        if self._is_running:
            self._queue_processor.schedule_stop()
            self._is_running = False
            if self._running_job is not None:
                # TODO Add an option to not cancel the currently running job?
                self._running_job.cancel()
            if self._queue_processor.is_running():
                # Wait for the thread to finish
                self._queue_processor.wait_stop()

    async def _handle_task(self, item):
        LOGGER.debug("Got task %s", item)  # TODO Do something with the item

    async def poll(self):
        await self._task_poller.poll(handle_task=self._handle_task)
