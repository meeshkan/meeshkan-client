import time
from concurrent.futures import Future, wait
import queue

import meeshkan
from meeshkan.scheduler import Scheduler, QueueProcessor
from meeshkan.job import Job, JobStatus, Executable
from meeshkan.notifiers import Notifier


# Executable that runs the provided `target` function
class TargetExecutable(Executable):
    def __init__(self, target, on_terminate=None):
        super().__init__()
        self._target = target
        self.on_terminate = on_terminate

    def wait(self):
        return self._target()

    def terminate(self):
        if self.on_terminate is not None:
            self.on_terminate()


# Executable that blocks until future is resolved
class FutureWaitingExecutable(Executable):
    def __init__(self, future):
        super().__init__()
        self._future = future

    def wait(self):
        results = wait([self._future])
        for result in results.done:
            return result.result()

    def terminate(self):
        self._future.set_result(-15)


def get_scheduler():
    queue_processor = QueueProcessor()
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


def wait_for_true(func, timeout=10):
    slept = 0
    time_to_sleep = 0.1
    while not func():
        time.sleep(time_to_sleep)
        slept += time_to_sleep
        if slept > timeout:
            raise Exception("Wait timeouted")


def test_job_submit():
    with get_scheduler() as scheduler:
        job = get_job(executable=get_executable(target=lambda: 0))
        scheduler.submit_job(job)
        submitted_jobs = scheduler.submitted_jobs
        assert len(submitted_jobs) == 1
        assert submitted_jobs[0] is job
    assert not scheduler._is_running


def test_scheduling():
    resolve_value = True
    future, resolve = get_future_and_resolve(value=resolve_value)

    with get_scheduler() as scheduler:
        job = get_job(executable=get_executable(target=resolve), job_number=0)
        scheduler.submit_job(job)
        result = future.result(timeout=5)
        assert result is resolve_value
        assert job.status == JobStatus.FINISHED


def test_notifiers():
    future, resolve = get_future_and_resolve(value=True)

    finished_jobs = []
    notified_jobs = []
    started_jobs = []

    class MockNotifier(Notifier):

        def notify_job_start(self, job: meeshkan.job.Job):
            started_jobs.append({'job': job})

        def notify_job_end(self, job: meeshkan.job.Job):
            finished_jobs.append({'job': job})

        def notify(self, job: meeshkan.job.Job, message: str = None) -> None:
            notified_jobs.append({'job': job})

    with get_scheduler() as scheduler:
        job_to_submit = get_job(executable=get_executable(target=resolve))
        scheduler.register_listener(MockNotifier())
        scheduler.submit_job(job_to_submit)
        future.result()
        assert len(started_jobs) == 1
        assert len(notified_jobs) == 0  # Not used atm
        assert len(finished_jobs) == 1
        assert finished_jobs[0]['job'] is job_to_submit


def test_terminating_job():
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=Future()))
        scheduler.submit_job(job)
        # Block until job launched
        wait_for_true(lambda: job.is_launched)
        scheduler.stop_job(job_id=job.id)
    # Job status can be checked only after clean-up is performed
    assert job.status == JobStatus.CANCELED


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
        wait_for_true(lambda: scheduler._task_queue.empty())

    # Job status should be checked only after clean-up is performed
    assert job1.is_launched
    assert job1.status == JobStatus.FINISHED

    assert not job2.is_launched
    assert job2.status == JobStatus.STALE


def test_stopping_scheduler():
    future = Future()
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=future))
        scheduler.submit_job(job)
        # Wait until processing has started. No easy way to check this at the moment.
        time.sleep(1)
        # Exit scheduler, should not block as `job.cancel()` is called
    assert job.is_launched
    assert job.status == JobStatus.CANCELED


def test_queue_processor_shutsdown_cleanly():
    task_queue = queue.Queue()
    queue_processor = QueueProcessor()

    def process_item(item):
        return None

    queue_processor.start(queue_=task_queue, process_item=process_item)
    assert queue_processor.is_running()
    queue_processor.schedule_stop()
    queue_processor.wait_stop()
    assert not queue_processor.is_running()


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
        assert item == test_string_1
        item2 = handled_queue.get(block=True)
        assert item2 == test_string_2
        assert task_queue.empty()
    finally:
        queue_processor.schedule_stop()
        queue_processor.wait_stop()
