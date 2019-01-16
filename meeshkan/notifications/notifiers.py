""" Notifiers for changes in job status"""
import logging
from typing import Callable, Any, List, Union, Optional, Dict
from pathlib import Path
import uuid
import shutil
import os


from .__types__ import NotificationType, NotificationStatus, NotificationWithStatusTime
from ..core.job import BaseJob, Job, JobStatus
from ..__types__ import Payload

LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class Notifier:
    def __init__(self, name: str = None):
        self._notification_history_by_job = dict()  # type: Dict[uuid.UUID, List[NotificationWithStatusTime]]
        self.name = name or self.__class__.__name__

    def __add_to_history(self, job_id: uuid.UUID, notification: NotificationWithStatusTime):
        """Adds given notification (with status) to the notifiers job history."""
        self._notification_history_by_job.setdefault(job_id, list()).append(notification)

    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[NotificationWithStatusTime]]:
        res = {self.name: list()}  # type: Dict[str, List[NotificationWithStatusTime]]
        if job_id in self._notification_history_by_job:
            res[self.name] = self._notification_history_by_job[job_id]
        return res

    def get_last_notification_status(self, job_id: uuid.UUID) -> Dict[str, Optional[NotificationWithStatusTime]]:
        """Returns the last notifications for this notifier and it's status.

        :returns Last notification with status for given job id, or None if no information for given job exists.
        """
        res = {self.name: None}  # type: Dict[str, Optional[NotificationWithStatusTime]]
        job_notifications = self.get_notification_history(job_id)[self.name]
        if job_notifications:
            res[self.name] = job_notifications[-1]
        return res

    def notify_job_start(self, job: BaseJob) -> None:
        try:
            self._notify_job_start(job)
            notification = NotificationWithStatusTime(NotificationType.JOB_START, NotificationStatus.SUCCESS)
            self.__add_to_history(job.id, notification)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Notifying job start failed")
            notification = NotificationWithStatusTime(NotificationType.JOB_START, NotificationStatus.FAILED)
            self.__add_to_history(job.id, notification)

    def notify_job_end(self, job: BaseJob) -> None:
        try:
            self._notify_job_end(job)
            notification = NotificationWithStatusTime(NotificationType.JOB_END, NotificationStatus.SUCCESS)
            self.__add_to_history(job.id, notification)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Notifying job end failed")
            notification = NotificationWithStatusTime(NotificationType.JOB_END, NotificationStatus.FAILED)
            self.__add_to_history(job.id, notification)

    def notify(self, job: BaseJob, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        try:
            self._notify(job, image_path, n_iterations, iterations_unit)
            notification = NotificationWithStatusTime(NotificationType.JOB_UPDATE, NotificationStatus.SUCCESS)
            self.__add_to_history(job.id, notification)
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception("Notifying job update failed")
            notification = NotificationWithStatusTime(NotificationType.JOB_UPDATE, NotificationStatus.FAILED)
            self.__add_to_history(job.id, notification)

    # Functions inheriting classes must implement

    def _notify_job_start(self, job: BaseJob) -> None:
        """Notifies of a job start. Raises exception for failure."""
        raise NotImplementedError

    def _notify_job_end(self, job: BaseJob) -> None:
        """Notifies of a job end. Raises exception for failure."""
        raise NotImplementedError

    def _notify(self, job: BaseJob, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        """
        Notifies job status. Raises exception for failure.
        :return:
        """
        raise NotImplementedError


class LoggingNotifier(Notifier):
    def __init__(self, name: str = None):  # pylint: disable=useless-super-delegation
        super().__init__(name)

    def log(self, job_id, message):
        LOGGER.debug("%s: Notified for job %s:\n\t%s", self.__class__.__name__, job_id, message)

    def _notify(self, job: BaseJob, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        """Logs job status update and saves image to job directory. Raises exception for failure."""
        if not isinstance(job, Job):
            # TODO Implement for SageMaker?
            return
        if not os.path.isdir(job.output_path):  # Copy image file to job directory
            # Caught by `notify`
            raise RuntimeError("Target directory {dir} does not exist!".format(dir=job.output_path))
        new_image_path = shutil.copy2(image_path, job.output_path)  # Will raise if image_path does not exist
        self.log(job.id, "#{itr} {units} (view at {link})".format(itr=n_iterations, units=iterations_unit,
                                                                  link=new_image_path))

    def _notify_job_start(self, job: BaseJob) -> None:
        """Notifies of a job start. Raises exception for failure."""
        self.log(job.id, "Job started")

    def _notify_job_end(self, job: BaseJob) -> None:
        """Notifies of a job end. Raises exception for failure."""
        self.log(job.id, "Job finished")


class CloudNotifier(Notifier):
    # How many lines from stderr to include in output
    N_LINES_FROM_STDERR = 50

    def __init__(self, post_payload: Callable[[Payload], Any],
                 upload_file: Callable[[Union[str, Path], bool], Optional[str]], name: str = None):
        super().__init__(name)
        self._post_payload = post_payload
        self._upload_file = upload_file

    def _notify_job_start(self, job: BaseJob) -> None:
        """Notifies of a job start. Raises exception for failure."""
        mutation = "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "created": job.created.isoformat() + "Z",  # Assume it's UTC
                     "description": job.description if isinstance(job, Job) else None}
        self._post(mutation, {"in": job_input})

    @staticmethod
    def _input_vars_for_failed(base_job: BaseJob):

        input_vars = {
            "job_id": str(base_job.id)
        }

        def parse_stderr(job: Job):
            # TODO Move this to be a method in `BaseJob` and implement for SageMaker
            stderr_path = job.stderr
            if stderr_path:
                with open(stderr_path, "r") as file:
                    # TODO Use tail instead for efficiency?
                    # return subprocess.check_output(['tail', '-10', filename])
                    lines = file.read().splitlines()
                    return "\n".join(lines[-CloudNotifier.N_LINES_FROM_STDERR:])
            else:
                stderr = None
            return stderr

        if isinstance(base_job, Job):
            input_vars["stderr"] = parse_stderr(job=base_job)

        return input_vars

    def _notify_job_end(self, job: BaseJob) -> None:
        """Notifies of a job end. Raises exception for failure."""
        LOGGER.debug("Notifying server of job with status %s", job.status)

        if job.status == JobStatus.FAILED:
            operation = "mutation NotifyJobFailed($in: JobFailedInput!) { notifyJobFailed(input: $in) }"
            operation_input_vars = CloudNotifier._input_vars_for_failed(job)
        else:
            operation = "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"
            operation_input_vars = {"id": str(job.id), "name": job.name, "number": job.number}
        self._post(operation, {"in": operation_input_vars})

    def _notify(self, job: BaseJob, image_path: str, n_iterations: int = -1, iterations_unit: str = "iterations"):
        """Notifies job status update. Raises exception for failure.
        Build and posts GraphQL query payload to the server.
        If given a valid image_path, uploads it before sending the message.

        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :param job:
        :param image_path:
        :param n_iterations:
        :param iterations_unit:
        :return:
        """
        # Attempt to upload image to cloud
        download_link = ""
        if os.path.isfile(image_path):
            try:  # Upload image if we're given a valid image path...
                # Second argument denotes whether or not we're expecting a download link/path
                download_link = self._upload_file(image_path, True)  # type: ignore
            except Exception:  # pylint:disable=broad-except
                LOGGER.error("Could not post image to cloud server!")

        # Send notification
        mutation = "mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!) {" \
                   "notifyJobScalarChangesWithImage(input: $in)" \
                   "}"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "iterationsN": n_iterations,  # Assume it's UTC
                     "iterationsUnit": iterations_unit,
                     "imageUrl": download_link}
        self._post(mutation, {"in": job_input})

    def _post(self, mutation, variables):
        payload = {"query": mutation, "variables": variables}
        self._post_payload(payload)
        LOGGER.info("Posted successfully: %s", variables)


class NotifierCollection(Notifier):
    def __init__(self, *notifiers):
        """Creates a messenger object, responsible of orchestrating notifiers and notifications.
        This class is guaranteed to not raise exceptions.

        :param notifiers: Optional list of notifiers to initialize the messenger with
        """
        super().__init__()
        self._notifiers = list()  # type: List[Notifier]
        for notifier in notifiers:
            self.register_notifier(notifier)

    # Methods to handle job notification history

    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[NotificationWithStatusTime]]:
        """Returns the notification history for given job"""
        history = dict()
        for notifier in self._notifiers:
            history.update(notifier.get_notification_history(job_id))
        return history

    def get_last_notification_status(self, job_id: uuid.UUID) -> Dict[str, Optional[NotificationWithStatusTime]]:
        history = dict()
        for notifier in self._notifiers:
            history.update(notifier.get_last_notification_status(job_id))
        return history

    # Methods to handle listeners

    def register_notifier(self, new_notifier: Notifier) -> bool:
        """Registers a new notifier. Fails if a notifier of that class is already registered. """
        # Verify new_notifier does not exist in the class yet
        for notifier in self._notifiers:
            if notifier.name == new_notifier.name:
                LOGGER.debug("Notifier of type %s already exists", new_notifier.name)
                return False
        LOGGER.debug("Registering notifier: %s", new_notifier.name)
        self._notifiers.append(new_notifier)
        return True

    # Methods to handle notifications

    def _notify_job_start(self, job: BaseJob) -> None:
        """Notifies of a job start."""
        for notifier in self._notifiers:
            notifier.notify_job_start(job)

    def _notify_job_end(self, job: BaseJob) -> None:
        """Notifies of a job end."""
        for notifier in self._notifiers:
            notifier.notify_job_end(job)

    def _notify(self, job: BaseJob, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        """
        Notifies job status update.
        :return:
        """
        for notifier in self._notifiers:
            notifier.notify(job, image_path, n_iterations, iterations_unit)
