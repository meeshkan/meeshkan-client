import pytest

from meeshkan.notifications.notifiers import CloudNotifier
from meeshkan.notifications.__types__ import NotificationStatus, NotificationType
from meeshkan.core.job import Executable, Job


def _get_job():
    return Job(Executable(), job_number=0)

def _empty_upload(image_url, download_link):
    pass

def test_cloud_notifier_job_start_end_queries():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    # Initializations (sanity checks)
    assert posted_payload == {}
    cloud_notifier = CloudNotifier(fake_post, _empty_upload)
    job = _get_job()
    expected_payload_start = {"query": "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"}
    expected_payload_end = {"query": "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"}

    notifications = cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
    assert len(notifications) == 0
    last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
    assert last_notification is None

    cloud_notifier.notify_job_start(job)

    # Validate query for notify_job_start
    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_start["query"]


    cloud_notifier.notify_job_end(job)

    # Validate query for notify_job_end
    assert "query" in posted_payload
    assert posted_payload["query"] == expected_payload_end["query"]

    assert "variables" in posted_payload
    variables = posted_payload["variables"]
    assert "in" in variables


def test_cloud_notifier_notifications():
    should_raise = False

    def _fake_post(payload):
        nonlocal should_raise
        if should_raise:
            raise RuntimeError

    cloud_notifier = CloudNotifier(_fake_post, _empty_upload)
    job = _get_job()

    cloud_notifier.notify_job_start(job)

    # Validate history for notify_job_start
    notifications = cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
    assert len(notifications) == 1
    assert notifications[0][0] == NotificationType.JOB_START
    assert notifications[0][1] == NotificationStatus.SUCCESS

    last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
    assert last_notification is not None
    assert last_notification[0] == NotificationType.JOB_START
    assert last_notification[1] == NotificationStatus.SUCCESS

    should_raise = True
    cloud_notifier.notify_job_end(job)

    # Validate history for notify_job_end
    notifications = cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
    assert len(notifications) == 2
    assert notifications[1][0] == NotificationType.JOB_END
    assert notifications[1][1] == NotificationStatus.FAILED

    last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
    assert last_notification is not None
    assert last_notification[0] == NotificationType.JOB_END
    assert last_notification[1] == NotificationStatus.FAILED


def test_cloud_notifier_job_update_no_image():
    posted_payload = {}

    def fake_post(payload):
        nonlocal posted_payload
        posted_payload = payload

    cloud_notifier = CloudNotifier(fake_post, _empty_upload)
    for path in ["fake_path", None]:
        cloud_notifier.notify(_get_job(), path, n_iterations=-1)

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
    cloud_notifier.notify(_get_job(), __file__, n_iterations=-1)

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
