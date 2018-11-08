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
    cloud_notifier.notifyJobStart(_get_job())

    expected_payload_start = {"query": "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"}
    expected_payload_end = {"query": "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"}

    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_start["query"]

    cloud_notifier.notifyJobEnd(_get_job())
    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_end["query"]

    assert "variables" in posted_payload
    variables = posted_payload["variables"]
    assert "in" in variables


def test_cloud_notifier_propagates_exception():
    def fake_post(payload):  # pylint:disable=unused-argument
        raise RuntimeError("Boom!")

    cloud_notifier = CloudNotifier(fake_post)
    with pytest.raises(RuntimeError):
        cloud_notifier.notify(_get_job())
