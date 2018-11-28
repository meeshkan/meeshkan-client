import pytest

from meeshkan.notifications.notifiers import CloudNotifier
from meeshkan.core.job import Executable, Job


def _get_job():
    return Job(Executable(), job_number=0)

def _empty_upload(image_url, download_link):
    pass

def test_cloud_notifier_job_start_end():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    assert posted_payload == {}
    cloud_notifier = CloudNotifier(fake_post, _empty_upload)
    cloud_notifier.notify_job_start(_get_job())

    expected_payload_start = {"query": "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"}
    expected_payload_end = {"query": "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"}

    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_start["query"]

    cloud_notifier.notify_job_end(_get_job())
    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_end["query"]

    assert "variables" in posted_payload
    variables = posted_payload["variables"]
    assert "in" in variables


def test_cloud_notifier_job_update_no_image():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    cloud_notifier = CloudNotifier(fake_post, _empty_upload)
    for path in ["fake_path", None]:
        cloud_notifier.notify(_get_job(), path)

        expected_payload = {'query': 'mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!)'
                                     ' {notifyJobScalarChangesWithImage(input: $in)}'}
        # Verify query structure
        assert 'query' in posted_payload
        assert posted_payload['query'] == expected_payload['query']
        assert 'variables' in posted_payload
        assert 'in' in posted_payload['variables']
        # Verify empty imageUrl
        variables = posted_payload['variables']['in']
        assert 'imageUrl' in variables
        assert variables['imageUrl'] == ''

def test_cloud_notifier_job_update_existing_file():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    def fake_upload(image_path, download_link):
        assert image_path == __file__
        return "no_upload"

    cloud_notifier = CloudNotifier(fake_post, fake_upload)
    cloud_notifier.notify(_get_job(), __file__)

    expected_payload = {'query': 'mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!)'
                                 ' {notifyJobScalarChangesWithImage(input: $in)}'}
    # Verify query structure
    assert 'query' in posted_payload
    assert posted_payload['query'] == expected_payload['query']
    assert 'variables' in posted_payload
    assert 'in' in posted_payload['variables']
    # Verify empty imageUrl
    variables = posted_payload['variables']['in']
    assert 'imageUrl' in variables
    assert variables['imageUrl'] == "no_upload"

def test_cloud_notifier_propagates_exception():
    def fake_post(payload):  # pylint:disable=unused-argument
        raise RuntimeError("Boom!")

    cloud_notifier = CloudNotifier(fake_post, _empty_upload)
    with pytest.raises(RuntimeError):
        cloud_notifier.notify(_get_job(), "")
