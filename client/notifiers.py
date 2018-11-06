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

    def notify(self, job: client.job.Job) -> None:
        """
        Notifies job status. Raises exception for failure.
        :param job:
        :return:
        """
        pass


def _build_job_notify_payload(job: client.job.Job) -> client.cloud.Payload:
    """
    Build GraphQL query payload to be sent to server.
    Schema of job_input MUST match with the server schema
    https://github.com/Meeshkan/meeshkan-cloud/blob/master/src/schema.graphql
    :param job:
    :return:
    """
    mutation = "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"

    job_input = {
        "id": str(job.id),
        "name": "name",
        "number": job.number,
        "created": job.created.isoformat() + "Z",  # Assume it's UTC
        "description": "description",
        "message": str(job.status)
    }
    payload: client.cloud.Payload = {
        "query": mutation,
        "variables": {
            "in": job_input
        }
    }
    return payload


class LoggingNotifier(Notifier):
    def __init__(self):
        super().__init__()

    def notify(self, job: client.job.Job) -> None:
        LOGGER.debug("%s: Notified for job %s", self.__class__.__name__,  job)


class CloudNotifier(Notifier):
    def __init__(self, post_payload: Callable[[client.cloud.Payload], None]):
        super().__init__()
        self._post_payload = post_payload

    def notify(self, job: client.job.Job) -> None:
        query_payload: client.cloud.Payload = _build_job_notify_payload(job)
        self._post_payload(query_payload)
        LOGGER.info(f"Posted successfully: %s", str(job))
