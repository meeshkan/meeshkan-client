""" Notifiers for changes in job status"""
import logging
from typing import Callable, Any, List, Union, Optional, Dict
from pathlib import Path
import uuid
import shutil
import os


from .__types__ import NotificationType, NotificationStatus, NotificationWithStatus
from ..core.config import JOBS_DIR
from ..core.job import Job
from ..__types__ import Payload
from ..exceptions import JobNotFoundException

LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class Notifier(object):
    def __init__(self, name: str = None):
        self._notification_history_by_job = dict()  # type: Dict[uuid.UUID, List[NotificationWithStatus]]
        self.name = name or self.__class__.__name__

    def __add_to_history(self, job_id: uuid.UUID, notification: NotificationWithStatus):
        self._notification_history_by_job.setdefault(job_id, list()).append(notification)

    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[NotificationWithStatus]]:
        res = {self.name: list()}
        if job_id in self._notification_history_by_job:
            res[self.name] = self._notification_history_by_job[job_id]
        return res

    def get_last_notification_status(self, job_id: uuid.UUID) -> Dict[str, Optional[NotificationWithStatus]]:
        """Returns the last notifications for this notifier and it's status.

        :returns Last notification with status for given job id, or None if no information for given job exists.
        """
        res = {self.name: None}
        job_notifications = self.get_notification_history(job_id)
        if job_notifications:
            res[self.name] = job_notifications[-1]
        return res

    def notify_job_start(self, job: Job) -> None:
        try:
            self._notify_job_start(job)
            self.__add_to_history(job.id, (NotificationType.JOB_START, NotificationStatus.SUCCESS))
        except:  # pylint: disable=broad-except
            self.__add_to_history(job.id, (NotificationType.JOB_START, NotificationStatus.FAILED))

    def notify_job_end(self, job: Job) -> None:
        try:
            self._notify_job_end(job)
            self.__add_to_history(job.id, (NotificationType.JOB_END, NotificationStatus.SUCCESS))
        except:  # pylint: disable=broad-except
            self.__add_to_history(job.id, (NotificationType.JOB_END, NotificationStatus.FAILED))

    def notify(self, job: Job, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        try:
            self._notify(job, image_path, n_iterations, iterations_unit)
            self.__add_to_history(job.id, (NotificationType.JOB_UPDATE, NotificationStatus.SUCCESS))
        except:  # pylint: disable=broad-except
            self.__add_to_history(job.id, (NotificationType.JOB_UPDATE, NotificationStatus.FAILED))

    # Functions inhereting classes must implement

    def _notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        raise NotImplementedError

    def _notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        raise NotImplementedError

    def _notify(self, job: Job, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        """
        Notifies job status. Raises exception for failure.
        :return:
        """
        raise NotImplementedError


class LoggingNotifier(Notifier):
    def __init__(self):  # pylint: disable=useless-super-delegation
        super().__init__()

    def log(self, job_id, message):
        LOGGER.debug("%s: Notified for job %s:\n\t%s", self.__class__.__name__, job_id, message)

    def _notify(self, job: Job, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        if os.path.isfile(image_path):
            # Copy image file to job directory
            new_image_path = shutil.copy2(image_path, JOBS_DIR.joinpath(str(job.id)))
            self.log(job.id, "#{itr} {units} (view at {link})".format(itr=n_iterations, units=iterations_unit,
                                                                      link=new_image_path))

    def _notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        self.log(job.id, "Job started")

    def _notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        self.log(job.id, "Job finished")


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], Any],
                 upload_file: Callable[[Union[str, Path], bool], Optional[str]]):
        super().__init__()
        self._post_payload = post_payload
        self._upload_file = upload_file

    def _notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        mutation = "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "created": job.created.isoformat() + "Z",  # Assume it's UTC
                     "description": job.description}
        self._post(mutation, {"in": job_input})

    def _notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        mutation = "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"
        job_input = {"id": str(job.id), "name": job.name, "number": job.number}
        self._post(mutation, {"in": job_input})

    def _notify(self, job: Job, image_path: str, n_iterations: int = -1, iterations_unit: str = "iterations") -> None:
        """Build and posts GraphQL query payload to the server.
        If given an image_path, uploads it before sending the message.

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
        if image_path is not None:
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


class NotifierCollection(object):
    def __init__(self, *args):
        """Creates a messenger object, responsible of orchestrating notifiers and notifications.
        This class is guaranteed to not raise exceptions.

        :param notifiers: Optional list of notifiers to initialize the messenger with
        """
        self._notifiers = list()  # type: List[Notifier]
        for notifier in args:
            self.register_notifier(notifier)

    # Methods to handle job notification history

    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[NotificationWithStatus]]:
        """Returns the notification history for given job"""
        history = dict()
        for notifier in self._notifiers:
            history.update(notifier.get_notification_history(job_id))
        return history

    def get_last_notification_status(self, job_id: uuid.UUID) -> Dict[str, Optional[NotificationWithStatus]]:
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

    def _notify_job_start(self, job: Job) -> None:
        """Notifies of a job start."""
        for notifier in self._notifiers:
            notifier.notify_job_start(job)

    def _notify_job_end(self, job: Job) -> None:
        """Notifies of a job end."""
        for notifier in self._notifiers:
            notifier.notify_job_end(job)

    def _notify(self, job: Job, image_path: str, n_iterations: int, iterations_unit: str = "iterations") -> None:
        """
        Notifies job status.
        :return:
        """
        for notifier in self._notifiers:
            notifier.notify(job, image_path, n_iterations, iterations_unit)
