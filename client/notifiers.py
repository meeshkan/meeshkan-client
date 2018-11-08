""" Notifiers for changes in job status"""
import logging
from typing import Callable

import client.job
import client.oauth
import client.exceptions
import client.cloud

LOGGER = logging.getLogger(__name__)


class Notifier(object):

    def __init__(self):
        pass

    def notify(self, job: client.job.Job, message: str = None) -> None:
        """
        Notifies job status. Raises exception for failure.
        :param job:
        :return:
        """
        raise NotImplementedError


class LoggingNotifier(Notifier):
    def __init__(self):
        super().__init__()

    def notify(self, job: client.job.Job, message: str = None) -> None:
        LOGGER.debug("%s: Notified for job %s\n\t%s", self.__class__.__name__, job, message)


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[client.cloud.Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: client.job.Job, message: str = None) -> None:
        """Build and posts GraphQL query payload to the server

        Schema of job_input MUST match with the server schema
        https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
        :param job:
        :param message: Meesage to include in the JobInput; otherwise uses job.status
        :return:
        """
        mutation = "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"
        job_input = {"id": str(job.id),
                     "name": str(job.name),
                     "number": job.number,
                     "created": job.created.isoformat() + "Z",  # Assume it's UTC
                     "description": job.description,
                     "message": message or str(job.status)}
        payload: client.cloud.Payload = {"query": mutation, "variables": {"in": job_input}}
        self._post_payload(payload)
        LOGGER.info(f"Posted successfully: %s", str(job))
