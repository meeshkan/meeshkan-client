""" Notifiers for changes in job status"""
import logging
from typing import Callable, Any, List

from .job import Job
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

    def notify(self, job: Job, image_url: str,
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

    def notify(self, job: Job, image_url: str, n_iterations: int,
               iterations_unit: str = "iterations") -> None:
        self.log(job.id, "#{itr} {msr} (view at {link})".format(itr=n_iterations, msr=iterations_unit, link=image_url))

    def notify_job_start(self, job: Job) -> None:
        """Notifies of a job start. Raises exception for failure."""
        self.log(job.id, "Job started")

    def notify_job_end(self, job: Job) -> None:
        """Notifies of a job end. Raises exception for failure."""
        self.log(job.id, "Job finished")


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[Payload], Any]):
        super().__init__()
        self._post_payload = post_payload

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

    def notify(self, job: Job, image_url: str, n_iterations: int = -1,
               iterations_unit: str = "iterations") -> None:
        """Build and posts GraphQL query payload to the server

        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :param job:
        :param image_url:
        :param n_iterations:
        :param iterations_unit:
        :return:
        """
        mutation = "mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!) {" \
                   "notifyJobScalarChangesWithImage(input: $in)" \
                   "}"
        job_input = {"id": str(job.id),
                     "name": job.name,
                     "number": job.number,
                     "iterationsN": n_iterations,  # Assume it's UTC
                     "iterationsUnit": iterations_unit,
                     "imageUrl": image_url}
        self._post(mutation, {"in": job_input})

    def _post(self, mutation, variables):
        payload = {"query": mutation, "variables": variables}
        self._post_payload(payload)
        LOGGER.info("Posted successfully: %s", variables)
