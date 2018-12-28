import time
from concurrent.futures import Future, wait
import queue

from meeshkan.notifications.notifiers import Notifier
from meeshkan.core.scheduler import Scheduler, QueueProcessor
from meeshkan.core.job import JobStatus, Executable, Job
from meeshkan.core.tasks import Task, TaskType

from .utils import MockNotifier, wait_for_true, FUTURE_TIMEOUT

import pytest

# Executable that runs the provided `target` function
class TargetExecutable(Executable):
    def __init__(self, target, on_terminate=None):
        super().__init__()
        self._target = target
        self.on_terminate = on_terminate

    def launch_and_wait(self):
        return self._target()

    def terminate(self):
        if self.on_terminate is not None:
            self.on_terminate()


# Executable that blocks until future is resolved
class FutureWaitingExecutable(Executable):
    def __init__(self, future):
        super().__init__()
        self._future = future

    def launch_and_wait(self):
        self.pid = True
        results = wait([self._future])
        for result in results.done:
            return result.result()

    def terminate(self):
        self._future.set_result(-15)


def get_scheduler(with_notifier=False):
    queue_processor = QueueProcessor()
    if with_notifier:
        scheduler = Scheduler(queue_processor, notifier=MockNotifier())
    else:
        scheduler = Scheduler(queue_processor=queue_processor)
    return scheduler


def get_listener():
    def notify(job, return_code):
        print("Finished")
    return notify


def get_executable(target, on_terminate=None):
    return TargetExecutable(target=target, on_terminate=on_terminate)


def get_job(executable, job_number=0):
    return Job(executable=executable, job_number=job_number)


def get_future_and_resolve(value=True):
    future = Future()

    def resolve():
        future.set_result(value)
        return 0

    return future, resolve


def test_job_submit():
    with get_scheduler() as scheduler:
        job = get_job(executable=get_executable(target=lambda: 0))
        scheduler.submit_job(job)
        submitted_jobs = scheduler.jobs
        assert len(submitted_jobs) == 1, "Only one job was submitted!"
        assert submitted_jobs[0] is job, "The submitted job must match the original job"
        assert len(scheduler.submitted_jobs) == 1, "Only one job was submitted!"
        assert scheduler.submitted_jobs[job.id] is job, "The key must match the job id and value must match job!"
    assert not scheduler.is_running, "Scheduler should stop running when __exit__'ing"


def test_scheduling():
    resolve_value = True
    future, resolve = get_future_and_resolve(value=resolve_value)

    with get_scheduler() as scheduler:
        job = get_job(executable=get_executable(target=resolve), job_number=0)
        scheduler.submit_job(job)
        result = future.result(timeout=5)
        assert result is resolve_value, "A `resolve` function should run immediately and set to resolve_value. "
        assert job.status == JobStatus.FINISHED, "The job should be finished after calling the target `resolve` method."


def test_notifiers():
    future, resolve = get_future_and_resolve(value=True)

    job_to_submit = get_job(executable=get_executable(target=resolve))
    with get_scheduler(with_notifier=True) as scheduler:
        scheduler.submit_job(job_to_submit)
        future.result(timeout=FUTURE_TIMEOUT)
        assert len(scheduler._notifier.started_jobs) == 1, "A job was submitted and must have started and ended by now"
        assert len(scheduler._notifier.notified_jobs) == 0, "The job was too short to capture any update-notifications"
        assert len(scheduler._notifier.finished_jobs) == 1, "The job must've ended as well!"
        assert scheduler._notifier.finished_jobs[0]['job'] is job_to_submit, "Finished job must match the submitted job"


def test_terminating_job():
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=Future()))
        scheduler.submit_job(job)
        # Block until job launched
        wait_for_true(lambda: job.is_launched)
        scheduler.stop_job(job_id=job.id)
    # Job status can be checked only after clean-up is performed
    assert job.status == JobStatus.CANCELED, "The job was cancelled shortly after it was launched!"


def test_canceling_job():
    future1 = Future()
    future2 = Future()
    with get_scheduler() as scheduler:
        job1 = get_job(executable=FutureWaitingExecutable(future=future1))
        job2 = get_job(executable=FutureWaitingExecutable(future=future2), job_number=1)
        scheduler.submit_job(job1)
        scheduler.submit_job(job2)
        # Cancel job2, should never run and therefore should be never have to be released
        scheduler.stop_job(job_id=job2.id)
        # Finish job1
        future1.set_result(result=0)
        # Block until there's nothing left in the queue
        wait_for_true(scheduler._job_queue.empty)

    # Job status should be checked only after clean-up is performed
    assert job1.is_launched, "The job was launched as soon as possible"
    assert job1.status == JobStatus.FINISHED, "And was done finished once called `set_result`"

    assert not job2.is_launched, "The job was never supposed to launch"
    assert job2.status == JobStatus.CANCELLED_BY_USER, "The job was cancelled immediately after submission, while " \
                                                       "another job was running"


def test_stopping_scheduler():
    future = Future()
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=future))
        scheduler.submit_job(job)
        # Wait until processing has started. No easy way to check this at the moment.
        while job.pid is None:
            time.sleep(0.1)
        # Exit scheduler, should not block as `job.cancel()` is called
    assert job.is_launched, "Job has started (as we wait for the PID to be available)"
    assert job.status == JobStatus.CANCELED, "The job was cancelled as the scheduler __exit__'d"


def test_queue_processor_shutsdown_cleanly():
    task_queue = queue.Queue()
    queue_processor = QueueProcessor()

    def process_item(item):
        return None

    queue_processor.start(queue_=task_queue, process_item=process_item)
    assert queue_processor.is_running(), "The QueueProcessor is expected to run while waiting for a task"
    queue_processor.schedule_stop()
    queue_processor.wait_stop()
    assert not queue_processor.is_running(), "The QueueProcessor was stopped - why is it still running?"


def test_queue_processor_processes_jobs():
    # Fill task queue
    task_queue = queue.Queue()
    test_string_1 = "Just testing"
    test_string_2 = "Here also"
    task_queue.put(test_string_1)
    task_queue.put(test_string_2)

    # Define handler that puts items to `handled_queue`
    handled_queue = queue.Queue()

    def process_item(item):
        handled_queue.put(item)

    # Start processing
    queue_processor = QueueProcessor()
    try:
        queue_processor.start(queue_=task_queue, process_item=process_item)
        item = handled_queue.get(block=True)
        assert item == test_string_1, "The first item to handle was '{}'!".format(test_string_1)
        item2 = handled_queue.get(block=True)
        assert item2 == test_string_2, "The second item to handle was '{}'!".format(test_string_2)
        assert task_queue.empty(), "There were only two items to handle, why is the queue not empty?"
    finally:
        queue_processor.schedule_stop()
        queue_processor.wait_stop()
