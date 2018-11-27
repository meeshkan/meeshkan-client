""" Notifiers for changes in job status"""
import logging
from typing import Callable, Any, List, Union, Optional
from pathlib import Path
import shutil
import os

from ..core.config import JOBS_DIR
from ..core.job import Job
from ..__types__ import Payload

LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class Notifier(object):
    def __init__(self):
        pass

    def notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        pass

    def notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        pass

    def notify(self, job: Job, image_path: str,
               n_iterations: int, iterations_unit: str = "iterations") -> None:
        """
        Notifies job status. Raises exception for failure.
        :return:
        """
        pass


class LoggingNotifier(Notifier):
    def __init__(self):  # pylint: disable=useless-super-delegation
        super().__init__()

    def log(self, job_id, message):
        LOGGER.debug("%s: Notified for job %s:\n\t%s", self.__class__.__name__, job_id, message)

    def notify(self, job: Job, image_path: str, n_iterations: int,
               iterations_unit: str = "iterations") -> None:
        if os.path.isfile(image_path):
            # Copy image file to job directory
            new_image_path = shutil.copy2(image_path, JOBS_DIR.joinpath(str(job.id)))
            self.log(job.id, "#{itr} {units} (view at {link})".format(itr=n_iterations, units=iterations_unit,
                                                                      link=new_image_path))

    def notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        self.log(job.id, "Job started")

    def notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        self.log(job.id, "Job finished")


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], Any],
                 upload_file: Callable[[Union[str, Path], bool], Optional[str]]):
        super().__init__()
        self._post_payload = post_payload
        self._upload_file = upload_file

    def notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        mutation = "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "created": job.created.isoformat() + "Z",  # Assume it's UTC
                     "description": job.description}
        self._post(mutation, {"in": job_input})

    def notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        mutation = "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"
        job_input = {"id": str(job.id), "name": job.name, "number": job.number}
        self._post(mutation, {"in": job_input})

    def notify(self, job: Job, image_path: str, n_iterations: int = -1,
               iterations_unit: str = "iterations") -> None:
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
                    download_link = self._upload_file(image_path, download_link=True)  # type: ignore
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
