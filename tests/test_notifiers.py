from .context import client
from client.notifiers import CloudNotifier, Payload, post_payloads, _build_query_payload
from client.job import Job, Executable
import pytest


def _get_job():
    return Job(Executable(), job_id=0)


def test_cloud_notifier():
    posted_payload = None

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    assert posted_payload is None
    cloud_notifier = CloudNotifier(fake_post)
    cloud_notifier.notify(_get_job())

    expected_payload = {"query": "{ hello }"}

    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload["query"]


def test_cloud_notifier_propagates_exception():
    def fake_post(payload):
        raise RuntimeError("Boom!")

    cloud_notifier = CloudNotifier(fake_post)
    with pytest.raises(RuntimeError):
        cloud_notifier.notify(_get_job())
