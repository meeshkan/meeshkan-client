""" Notifiers for changes in job status"""
import logging
from typing import Callable, Any

import meeshkan.job
import meeshkan.oauth
import meeshkan.exceptions
import meeshkan.cloud

LOGGER = logging.getLogger(__name__)


class Notifier(object):
    def __init__(self):
        pass

    def notify_job_start(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        pass

    def notify_job_end(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        pass

    def notify(self, job: meeshkan.job.Job, message: str = None) -> None:
        """
        Notifies job status. Raises exception for failure.
        :return:
        """
        pass


class LoggingNotifier(Notifier):
    def __init__(self):  # pylint: disable=useless-super-delegation
        super().__init__()

    def notify(self, job: meeshkan.job.Job, message: str = None) -> None:
        LOGGER.debug("%s: Notified for job %s\n\t%s", self.__class__.__name__, job, message)

    def notify_job_start(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        self.notify(job, "Job started")

    def notify_job_end(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        self.notify(job, "Job finished")


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[meeshkan.Payload], Any]):
        super().__init__()
        self._post_payload = post_payload

    def notify_job_start(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        mutation = "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "created": job.created.isoformat() + "Z",  # Assume it's UTC
                     "description": job.description}
        self._post(mutation, {"in": job_input})

    def notify_job_end(self, job: meeshkan.job.Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        mutation = "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"
        job_input = {"id": str(job.id), "name": job.name, "number": job.number}
        self._post(mutation, {"in": job_input})

    def notify(self, job: meeshkan.job.Job, message: str = None) -> None:
        """Build and posts GraphQL query payload to the server

        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :param job:
        :param message: Does not do anything
        :return:
        """
        mutation = ("mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!)",
                    "{ notifyJobScalarChangesWithImage(input: $in) }")
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "iterations": job.created.isoformat() + "Z",  # Assume it's UTC
                     "imageUrl": job.description}
        self._post(mutation, {"in": job_input})

    def _post(self, mutation, variables):
        payload = {"query": mutation, "variables": variables}
        self._post_payload(payload)
        LOGGER.info("Posted successfully: %s", variables)
