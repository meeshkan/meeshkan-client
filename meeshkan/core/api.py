from typing import Callable, Any, Tuple, List, Optional, Dict
import logging
import uuid
from pathlib import Path
from fnmatch import fnmatch

import Pyro4
import Pyro4.errors

from .job import Job, SageMakerJob, ExternalJob
from .sagemaker_monitor import SageMakerJobMonitor
from .scheduler import Scheduler
from .service import Service
from .tasks import TaskPoller, Task, TaskType
from ..notifications.notifiers import Notifier
from ..__types__ import HistoryByScalar
from .serializer import Serializer

__all__ = []  # type: List[str]

LOGGER = logging.getLogger(__name__)


class ExternalJobsApi:
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler

    @Pyro4.expose
    def create_external_job(self, pid: int, name: str,
                            poll_interval: Optional[float] = None) -> uuid.UUID:
        """
        Create a new external job and set it as active so that incoming reports with the same
        PID are registered to this job.
        :param pid: Process ID of creating process
        :param name: Job name
        :param poll_interval: Report interval in seconds
        :return: Job ID
        """
        external_job = ExternalJob.create(pid=pid, name=name, poll_interval=poll_interval)
        self.scheduler.external_jobs[external_job.id] = external_job
        return external_job.id

    @Pyro4.expose
    def register_active_external_job(self, job_id: uuid.UUID):
        self.scheduler.register_external_job(job_id=job_id)

    @Pyro4.expose
    def unregister_active_external_job(self, job_id: uuid.UUID):
        self.scheduler.unregister_external_job(job_id)


@Pyro4.behavior(instance_mode="single")  # Singleton
class Api:
    """Partially exposed by the Pyro server for communications with the CLI."""

    # Private methods
    def __init__(self, scheduler: Scheduler, service: Service = None, task_poller: TaskPoller = None,
                 sagemaker_job_monitor: Optional[SageMakerJobMonitor] = None, notifier: Notifier = None):
        self.scheduler = scheduler
        self.service = service
        self.sagemaker_job_monitor = sagemaker_job_monitor
        self.task_poller = task_poller
        self.notifier = notifier
        self.__stop_callbacks = []  # type: List[Callable[[], None]]
        self.__was_shutdown = False
        self._external_jobs = ExternalJobsApi(scheduler=self.scheduler)

    def __enter__(self):
        self.scheduler.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @Pyro4.expose  # type: ignore
    @property
    def external_jobs(self):
        return self._external_jobs

    def register_with_pyro(self, daemon: Pyro4.Daemon, name: str):
        daemon.register(self, name)
        # Add `external_jobs` proxy:
        # https://pyro4.readthedocs.io/en/stable/servercode.html#autoproxying
        daemon.register(self._external_jobs)

    def get_notification_status(self, job_id: uuid.UUID) -> str:
        """Returns last notification status for job_id
        """
        if self.notifier:
            # results hold a Dict[str, Optional[NotificationWithStatus]] where str is name of notifier
            results = self.notifier.get_last_notification_status(job_id)
            # Reformat for a string (dictionary has only one key in this instance)
            res_list = []
            for notifier, result in results.items():
                if result is not None:
                    res_list.append("{notifier}: {notification} ({result})".format(notification=result.type.name,
                                                                                   notifier=notifier,
                                                                                   result=result.status.name))
            return '\n'.join(res_list)
        return ""

    async def handle_task(self, task: Task):
        LOGGER.debug("Got task for job ID %s, task type %s", task.job_id, task.type.name)
        if task.type == TaskType.StopJobTask:
            self.scheduler.stop_job(task.job_id)

    async def poll(self):
        if self.task_poller is not None:
            await self.task_poller.poll(handle_task=self.handle_task)

    # Exposed methods

    @Pyro4.expose
    def cancel_job(self, job_id: uuid.UUID):
        self.scheduler.stop_job(job_id)

    @Pyro4.expose
    def get_job(self, job_id: uuid.UUID) -> Optional[Job]:
        return self.scheduler.submitted_jobs.get(job_id)

    @Pyro4.expose
    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[str]]:
        """Returns the entire notification history for a given job ID. Returns an empty dictionary if no notifier
        is available."""
        if self.notifier:
            notification_history = self.notifier.get_notification_history(job_id)
            # Normalize the data to human-readable format
            new_table_history = dict()  # type: Dict[str, List[str]]
            for notifier_name, notifier_history in notification_history.items():
                formatted_history = list()
                for entry in notifier_history:
                    formatted_history.append("[{time}] {type}: {status}".format(time=entry.time, type=entry.type.name,
                                                                                status=entry.status.name))
                new_table_history[notifier_name] = formatted_history
            return new_table_history
        return dict()

    @Pyro4.expose
    def find_job_id(self, job_id: uuid.UUID = None, job_number: int = None, pattern: str = None) -> Optional[uuid.UUID]:
        """Finds a job from the scheduler given one of the arguments.
        Operator precedence if given multiple arguments is: UUID, job_number, pattern.

        :return Job UUID if a mathing job is found. Otherwise returns None.
        """
        def filter_jobs(condition: Callable[[Job], bool]) -> Optional[uuid.UUID]:
            matching_jobs = [job.id for job in self.scheduler.jobs if condition(job)]  # type: List[uuid.UUID]
            if matching_jobs:
                return matching_jobs[0]
            return None

        if job_id is None and job_number is None and pattern is None:  # No arguments given?
            return None

        if job_id is not None:  # Match by UUID
            job = self.get_job(job_id)
            if isinstance(job, Job):  # mypy understands this better than "is not None"
                return job.id

        if job_number is not None:  # Match by job number
            res = filter_jobs(lambda job: job.number == job_number)
            if res:
                return res

        if pattern is not None and pattern:
            # MyPy complains about `pattern` being Optional[str], but we check for validity so we ignore the error
            res = filter_jobs(lambda job: fnmatch(job.name, pattern))  # type: ignore
            if res:
                return res

        return None

    @Pyro4.expose
    def get_job_output(self, job_id: uuid.UUID) -> Tuple[Path, Path, Path]:
        """For a given job, return the job's output path, stderr and stdout."""
        job = self.scheduler.submitted_jobs[job_id]
        return job.output_path, job.stderr, job.stdout

    @Pyro4.expose
    def submit(self, args: Tuple[str, ...], cwd: str = None, name=None, poll_interval=None):
        job_number = len(self.scheduler.jobs) + 1
        job = Job.create_job(args, cwd=cwd, job_number=job_number, name=name, poll_interval=poll_interval)
        self.scheduler.submit_job(job)
        return job

    @Pyro4.expose
    def monitor_sagemaker(self, job_name: str, poll_interval: Optional[float] = None) -> SageMakerJob:
        """
        Start monitoring a SageMaker training job
        :param job_name: SageMaker training job name
        :param poll_interval: Polling interval in seconds
        :return: SageMakerJob instance
        """
        if not self.sagemaker_job_monitor:
            raise RuntimeError("SageMaker job monitor not defined.")

        job = self.sagemaker_job_monitor.create_job(job_name, poll_interval=poll_interval)
        if job.status.is_processed:
            return job
        self.sagemaker_job_monitor.start(job)
        # TODO self.job_store.include_as_job(job)
        return job

    @Pyro4.expose
    def list_jobs(self):
        jobs = list()
        for job in self.scheduler.submitted_jobs.values():  # Only list submitted jobs for now, not blocking ones
            temp_job_dict = job.to_dict()
            temp_job_dict['last notification status'] = self.get_notification_status(job.id)
            jobs.append(temp_job_dict)
        return jobs

    @Pyro4.expose
    def add_stop_callback(self, func: Callable[[], Any]):
        self.__stop_callbacks.append(func)

    @Pyro4.expose
    def report_scalar(self, pid, name, val):
        """Attempts to report a scalar update for process PID"""
        self.scheduler.report_scalar(pid, name, val)

    @Pyro4.expose
    def add_condition(self, pid: int, serialized_condition: str, only_relevant: bool, *vals: str):
        """Sets a condition for notifications"""
        self.scheduler.add_condition(pid, *vals, condition=Serializer.deserialize(serialized_condition),
                                     only_relevant=only_relevant)

    @Pyro4.expose
    def get_updates(self, job_id: uuid.UUID) -> HistoryByScalar:
        vals, _ = self.scheduler.query_scalars(job_id=job_id, latest_only=False, plot=False)
        # We leave the recent_vals in a list for easy use in tabulate
        recent_vals = {val_name: values[-1:] for val_name, values in vals.items()}
        return recent_vals

    @Pyro4.expose
    def stop(self):
        if self.__was_shutdown:
            LOGGER.warning("Agent API was shutdown twice.")
            return
        self.__was_shutdown = True
        self.scheduler.stop()
        if self.service is not None:
            self.service.stop()
        for callback in self.__stop_callbacks:
            callback()
