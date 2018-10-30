from .context import client
from client.scheduler import Scheduler
from client.job import Job, JobStatus, Executable
from concurrent.futures import Future, wait
import time


# Executable that runs the provided `target` function
class TargetExecutable(Executable):
    def __init__(self, target, on_terminate=None):
        super().__init__()
        self._target = target
        self.on_terminate = on_terminate
        pass

    def launch_and_wait(self):
        return self._target()

    def terminate(self):
        if self.on_terminate is not None:
            self.on_terminate()
        return


# Executable that blocks until future is resolved
class FutureWaitingExecutable(Executable):
    def __init__(self, future):
        super().__init__()
        self._future = future
        pass

    def launch_and_wait(self):
        results = wait([self._future])
        for result in results.done:
            return result.result()

    def terminate(self):
        self._future.set_result(-15)
        return


def get_scheduler():
    scheduler = Scheduler()
    return scheduler


def get_listener():
    def notify(job, return_code):
        print("Finished")
    return notify


def get_executable(target, on_terminate=None):
    return TargetExecutable(target=target, on_terminate=on_terminate)


def get_job(executable, job_id=0):
    return Job(executable=executable, job_id=job_id)


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
    return


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
        job = get_job(executable=get_executable(target=resolve), job_id=0)
        scheduler.submit_job(job)
        results = wait([future], timeout=5)
        assert len(results.done) == 1
        for result in results.done:
            assert result.result() is resolve_value
        assert job.status == JobStatus.FINISHED


def test_notifiers():
    future, resolve = get_future_and_resolve(value=True)

    finished_jobs = []

    def notify(job0, return_code):
        finished_jobs.append({'job': job0, 'return_code': return_code})

    with get_scheduler() as scheduler:
        job = get_job(executable=get_executable(target=resolve), job_id=0)
        scheduler.register_listener(notify)
        scheduler.submit_job(job)
        wait([future], timeout=5)
        assert len(finished_jobs) == 1
        assert finished_jobs[0]['return_code'] == 0
        assert finished_jobs[0]['job'] is job


def test_terminating_job():
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=Future()), job_id=0)
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
        job1 = get_job(executable=FutureWaitingExecutable(future=future1), job_id=0)
        job2 = get_job(executable=FutureWaitingExecutable(future=future2), job_id=1)
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
    assert job2.status == JobStatus.CANCELED


def test_stopping_scheduler():
    future = Future()
    with get_scheduler() as scheduler:
        job = get_job(executable=FutureWaitingExecutable(future=future), job_id=0)
        scheduler.submit_job(job)
        # Wait until processing has started
        wait_for_true(lambda: scheduler._task_queue.empty())
        # Exit scheduler, should not block as `job.cancel()` is called
    assert job.is_launched
    assert job.status == JobStatus.CANCELED
