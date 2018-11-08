import pytest

from client.notifiers import CloudNotifier
from client.job import Job, Executable


def _get_job():
    return Job(Executable(), job_number=0)


def test_cloud_notifier():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    assert posted_payload == {}
    cloud_notifier = CloudNotifier(fake_post)
    cloud_notifier.notify(_get_job())

    expected_payload = {"query": "mutation NotifyJob($in: JobInput!) { notifyJob(input: $in) }"}

    assert "query" in posted_payload

    assert posted_payload["query"] == expected_payload["query"]

    assert "variables" in posted_payload
    variables = posted_payload["variables"]
    assert "in" in variables


def test_cloud_notifier_propagates_exception():
    def fake_post(payload):  # pylint:disable=unused-argument
        raise RuntimeError("Boom!")

    cloud_notifier = CloudNotifier(fake_post)
    with pytest.raises(RuntimeError):
        cloud_notifier.notify(_get_job())


