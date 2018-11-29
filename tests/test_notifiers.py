from unittest import mock
from pathlib import Path
import shutil
import pytest

from meeshkan.notifications.notifiers import CloudNotifier, LoggingNotifier, NotifierCollection
from meeshkan.notifications.__types__ import NotificationStatus, NotificationType
from meeshkan.core.job import Executable, Job
from meeshkan.core.config import JOBS_DIR


def _get_job():
    return Job(Executable(), job_number=0)

def _empty_upload(image_url, download_link):
    pass

def _empty_post(payload):
    pass


# LoggingNotifier Tests
def test_logging_notifier_job_start_end():
    """Tests the job start/end for Logging Notifier"""
    result = dict()
    def fake_log(self, job_id, message):
        # No need to check with exceptions (for history management), as it's checked in another test
        nonlocal result
        result[job_id] = message

    job = _get_job()
    assert len(result) == 0

    with mock.patch('meeshkan.notifications.notifiers.LoggingNotifier.log', fake_log):
        logging_notifier = LoggingNotifier()
        logging_notifier.notify_job_start(job)
        # Verify internal state
        assert len(result) == 1
        assert job.id in result
        assert "Job started" in result[job.id]

        logging_notifier.notify_job_end(job)
        # Verify internal state
        assert len(result) == 1
        assert job.id in result
        assert "Job finished" in result[job.id]


def test_logging_notifier_job_update():
    """Tests the job update for LoggingNotifier when either image or directory do not exist, and when both exist"""
    result = dict()
    def fake_log(self, job_id, message):
        # No need to check with exceptions (for history management), as it's checked in another test
        nonlocal result
        result[job_id] = message

    assert len(result) == 0

    job = _get_job()
    logging_notifier = LoggingNotifier()

    # Job directory doesn't exist but file does exist -> expected a failure in notification!
    logging_notifier.notify(job, __file__, -1)
    last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
    assert last_notification[0] == NotificationType.JOB_UPDATE
    assert last_notification[1] == NotificationStatus.FAILED

    # Job directory exists but file doesn't -> expected a failure in notification still!
    target_dir = JOBS_DIR.joinpath(str(job.id))
    target_dir.mkdir()

    logging_notifier.notify(job, "does_not_exist", -1)
    last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
    assert last_notification[0] == NotificationType.JOB_UPDATE
    assert last_notification[1] == NotificationStatus.FAILED

    # Both exist!
    with mock.patch('meeshkan.notifications.notifiers.LoggingNotifier.log', fake_log):
        logging_notifier = LoggingNotifier()
        logging_notifier.notify(job, __file__, -1)
        last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
        assert last_notification[0] == NotificationType.JOB_UPDATE
        assert last_notification[1] == NotificationStatus.SUCCESS
        assert len(result) == 1
        assert job.id in result
        assert "view at" in result[job.id]

    # Cleanup
    shutil.rmtree(target_dir, ignore_errors=True)


# CloudNotifier Tests
def test_cloud_notifier_job_start_end_queries():
    """Tests the job start/end for CloudNotifier"""
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


def test_cloud_notifier_job_update_no_image():
    """Tests the job update for CloudNotifier when no image is available or image does not exist"""
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
    """Tests the job update for CloudNotifier when the image exists and is valid"""
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


# General Notifier Tests
def test_notifier_history():
    """Tests the Notifier's built-in history management via CloudNotifier"""
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


# NotifierCollection Tests
def test_notifier_collection_notifiers_init():
    """Tests init with notifiers"""
    cloud_notifier = CloudNotifier(_empty_post, _empty_upload)
    logging_notifier = LoggingNotifier()

    # Proper init
    collection = NotifierCollection(*[cloud_notifier, logging_notifier])
    assert len(collection._notifiers) == 2
    assert cloud_notifier in collection._notifiers and logging_notifier in collection._notifiers

    # Empty init
    collection = NotifierCollection()
    assert len(collection._notifiers) == 0

    # Bad init
    collection = NotifierCollection(*[cloud_notifier, cloud_notifier])
    assert len(collection._notifiers) == 1


def test_notifier_collection_registering_notifiers():
    """Tests the register_notifier method"""
    cloud_notifier = CloudNotifier(_empty_post, _empty_upload)
    cloud_notifier2 = CloudNotifier(_empty_post, _empty_upload, name="smeagol")
    collection = NotifierCollection()

    # Sanity check
    assert len(collection._notifiers) == 0

    # Adding
    assert collection.register_notifier(cloud_notifier)
    assert len(collection._notifiers) == 1

    # Adding again?
    assert not collection.register_notifier(cloud_notifier)

    # Adding same class, different name
    assert collection.register_notifier(cloud_notifier2)
    assert len(collection._notifiers) == 2


def test_notifier_collection_notifications():
    """Tests the job notifications are sent to all registered notifiers, along with history management"""
    cloud_counter = 0
    logging_counter = 0

    def fake_post(payload):
        nonlocal cloud_counter
        cloud_counter += 1

    def fake_log(self, job_id, message):
        nonlocal logging_counter
        logging_counter += 1

    job = _get_job()
    with mock.patch('meeshkan.notifications.notifiers.LoggingNotifier.log', fake_log):
        cloud_notifier = CloudNotifier(fake_post, _empty_upload)
        logging_notifier = LoggingNotifier()
        collection = NotifierCollection(*[cloud_notifier, logging_notifier])

        # Test with notify_job_start
        collection.notify_job_start(job)
        assert cloud_counter == logging_counter == 1

        # Test with notify_job_end
        collection.notify_job_end(job)
        assert cloud_counter == logging_counter == 2

        # Test with notify
        collection.notify(job, "", -1)
        # Validate `notify` via job_history
        last_notification = collection.get_last_notification_status(job.id)
        assert len(last_notification) == 2
        assert cloud_notifier.name in last_notification
        assert logging_notifier.name in last_notification
        assert last_notification[cloud_notifier.name][0] == NotificationType.JOB_UPDATE
        assert last_notification[logging_notifier.name][0] == NotificationType.JOB_UPDATE
        # Cloud notification is expected to be successful as we emulate the upload and posting process
        assert last_notification[cloud_notifier.name][1] == NotificationStatus.SUCCESS
        # Logging notification is expected to fail as the target directory does not exist
        assert last_notification[logging_notifier.name][1] == NotificationStatus.FAILED

        # Test history
        history = collection.get_notification_history(job.id)
        assert len(history) == 2
        assert cloud_notifier.name in last_notification
        assert logging_notifier.name in last_notification
        cloud_history = history[cloud_notifier.name]
        logging_history = history[logging_notifier.name]
        assert cloud_history == cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
        assert logging_history == logging_notifier.get_notification_history(job.id)[logging_notifier.name]
