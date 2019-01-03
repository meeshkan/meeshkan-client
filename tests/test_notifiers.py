# pylint: disable=no-self-use  # To avoid warnings with classes used to group tests
import os
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock
import uuid
import shutil
import pytest

from meeshkan.notifications.notifiers import CloudNotifier, LoggingNotifier, NotifierCollection
from meeshkan.notifications.__types__ import NotificationStatus, NotificationType
from meeshkan.core.job import Executable, Job, JobStatus
from meeshkan.core.config import JOBS_DIR


@pytest.fixture
def cleanup():
    yield None
    # Post-test code
    shutil.rmtree(_get_job().output_path, ignore_errors=True)


def _get_job():
    job_id = uuid.uuid4()
    target_dir = JOBS_DIR.joinpath(str(job_id))
    return Job(Executable(output_path=target_dir), job_number=0, job_uuid=job_id)


def _empty_upload(image_url, download_link):
    pass


def _empty_post(payload):
    pass


@pytest.mark.usefixtures("cleanup")
class TestLoggingNotifier:
    # LoggingNotifier Tests
    def test_logging_notifier_job_start_end(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job start/end for Logging Notifier"""
        result = dict()
        def fake_log(self, job_id, message):
            # No need to check with exceptions (for history management), as it's checked in another test
            nonlocal result
            result[job_id] = message

        job = _get_job()
        assert len(result) == 0, "Sanity test - `result` dictionary should be empty at this point"

        with mock.patch('meeshkan.notifications.notifiers.LoggingNotifier.log', fake_log):
            logging_notifier = LoggingNotifier()
            logging_notifier.notify_job_start(job)
            # Verify internal state
            assert len(result) == 1, "There should be a single key-value pair " \
                                     "in `result` pertaining to the submitted job"
            assert job.id in result, "The key should match the job ID '{}'".format(job.id)
            assert "Job started" in result[job.id], "The notification should be about the 'Job Start' event"

            logging_notifier.notify_job_end(job)
            # Verify internal state
            assert len(result) == 1, "There should be a single key-value pair in " \
                                     "`result` pertaining to the submitted job"
            assert job.id in result, "The key should match the job ID '{}'".format(job.id)
            assert "Job finished" in result[job.id], "The notification should be about the 'Job End' event"

    def test_logging_notifier_job_update_no_file_no_dir(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job update for LoggingNotifier when neither image or directory exist"""
        job = _get_job()
        logging_notifier = LoggingNotifier()

        # Job directory doesn't exist but file does exist -> expected a failure in notification!
        logging_notifier.notify(job, __file__, -1)
        # Assumes this works from previous tests (and onwards)
        last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
        assert last_notification.type == NotificationType.JOB_UPDATE, "The notification type should be an update " \
                                                                      "pertaining to the job"
        assert last_notification.status == NotificationStatus.FAILED, "The notification should fail " \
                                                                      "when the Job output " \
                                                                      "path does not exist."

    def test_logging_notifier_job_update_no_file_with_dir(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job update for LoggingNotifier when an image doesn't exist bu the directory does"""
        job = _get_job()
        logging_notifier = LoggingNotifier()

        job.output_path.mkdir()
        # Job directory exists but file doesn't -> expected a failure in notification still!
        logging_notifier.notify(job, "does_not_exist", -1)
        last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
        assert last_notification.type == NotificationType.JOB_UPDATE, "The notification type should be an update " \
                                                                      "pertaining to the job"
        assert last_notification.status == NotificationStatus.FAILED, "The notification should fail " \
                                                                      "when the plot file " \
                                                                      "does not exist."

        # Cleanup
        shutil.rmtree(job.output_path, ignore_errors=True)

    def test_logging_notifier_job_update_file_dir(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job update for LoggingNotifier when both image and directory exist"""
        result = dict()

        def fake_log(self, job_id, message):
            # No need to check with exceptions (for history management), as it's checked in another test
            nonlocal result
            result[job_id] = message

        assert len(result) == 0, "Sanity test - `result` dictionary should be empty at this point"

        job = _get_job()
        logging_notifier = LoggingNotifier()

        job.output_path.mkdir()
        logging_notifier.notify(job, __file__, -1)
        # Both exist!
        with mock.patch('meeshkan.notifications.notifiers.LoggingNotifier.log', fake_log):
            logging_notifier = LoggingNotifier()
            logging_notifier.notify(job, __file__, -1)
            last_notification = logging_notifier.get_last_notification_status(job.id)[logging_notifier.name]
            assert last_notification.type == NotificationType.JOB_UPDATE, "The notification type should be an update " \
                                                                          "pertaining to the job"
            assert last_notification.status == NotificationStatus.SUCCESS, "With both folder and " \
                                                                           "image path existing, " \
                                                                           "the notification is expected to succeed."
            assert len(result) == 1, "There should only be one key-value pair for `result`"
            assert job.id in result, "The key should match the job ID '{}'".format(job.id)
            assert "view at" in result[job.id], "The notification should point to the plot"


@pytest.fixture
def job():
    yield _get_job()
    return None


@pytest.mark.usefixtures("cleanup")
class TestCloudNotifier:
    # CloudNotifier Tests
    def test_cloud_notifier_job_start_end_queries(self, job):  # pylint:disable=redefined-outer-name
        """Tests the job start/end for CloudNotifier"""
        posted_payload = {}

        def fake_post(payload):
            nonlocal posted_payload
            posted_payload = payload

        # Initializations (sanity checks)
        assert posted_payload == {}, "Sanity test - `posted_payload` dictionary should be empty at this point"
        cloud_notifier = CloudNotifier(fake_post, _empty_upload)
        expected_payload_start = {"query": "mutation NotifyJobStart($in: JobStartInput!) { notifyJobStart(input: $in) }"}
        expected_payload_end = {"query": "mutation NotifyJobEnd($in: JobDoneInput!) { notifyJobDone(input: $in) }"}

        notifications = cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
        assert len(notifications) == 0, "Expecting no notification at this point as no events have occurred"
        last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
        assert last_notification is None, "There is no last notification either, expected `None` value"

        cloud_notifier.notify_job_start(job)

        # Validate query for notify_job_start
        assert "query" in posted_payload, "Payload is expected to contain the key 'query'"
        assert posted_payload["query"] == expected_payload_start["query"], "GraphQL queries should be identical"

        cloud_notifier.notify_job_end(job)

        # Validate query for notify_job_end
        assert "query" in posted_payload, "Payload is expected to contain the key 'query'"
        assert posted_payload["query"] == expected_payload_end["query"], "GraphQL queries should be identical"

        assert "variables" in posted_payload, "Posted payload is expected to contain a 'variables' key"
        variables = posted_payload["variables"]
        assert "in" in variables, "'variables' dictionary is expected to contain a key called 'in'"

    def test_cloud_notifier_notifies_failed_job_with_correct_payload(self):
        fake_post = MagicMock()
        fake_upload = MagicMock()
        cloud_notifier = CloudNotifier(fake_post, fake_upload)

        def get_failed_job():
            job_id = uuid.uuid4()
            resource_dir = Path(os.path.dirname(__file__)).joinpath('resources', 'logs')
            job = Job(Executable(output_path=resource_dir), job_number=0, job_uuid=job_id)
            job.status = JobStatus.FAILED
            return job

        job = get_failed_job()

        cloud_notifier.notify_job_end(job)
        notification_status = cloud_notifier.get_last_notification_status(job.id)
        cloud_notification_status = notification_status["CloudNotifier"]
        assert cloud_notification_status.status == NotificationStatus.SUCCESS, "Notification status should be success"

        # Posted payload
        fake_post.assert_called_once()
        call_args = fake_post.call_args
        args, _ = call_args
        assert len(args) == 1, "Expected mock post to have been called with one argument"

        payload = args[0]
        assert payload is not None, "Expected posted payload to not be None"

        # Query
        assert "query" in payload, "Expected posted payload to have query field"
        query = payload["query"]
        assert query is not None

        # Variables
        assert "variables" in payload, "Expected posted payload to have variables field"
        variables = payload["variables"]
        assert variables is not None

        assert "in" in variables, "Expected variables to have 'in' field"
        inp = variables["in"]

        stderr = inp["stderr"]
        assert stderr is not None
        assert len(stderr) > 50

        assert inp["job_id"] is not None

    def test_cloud_notifier_job_update_no_image(self):  # pylint:disable=unused-argument,redefined-outer-name
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
            assert 'query' in posted_payload, "Payload is expected to contain the key 'query'"
            assert posted_payload['query'] == expected_payload['query'], "GraphQL queries should be identical"
            assert 'variables' in posted_payload, "Payload is expected to contain the key 'variables'"
            assert 'in' in posted_payload['variables'], "'variables' dictionary is expected " \
                                                        "to contain a key called 'in'"
            # Verify empty imageUrl
            variables = posted_payload['variables']['in']
            assert 'imageUrl' in variables, "'in' dictionary is expected to contain a key called 'imageUrl'"
            assert variables['imageUrl'] == '', "`imageUrl` value is expected to be empty"

    def test_cloud_notifier_job_update_existing_file(self, job):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job update for CloudNotifier when the image exists and is valid"""
        posted_payload = {}

        def fake_post(payload):
            nonlocal posted_payload
            posted_payload = payload

        def fake_upload(image_path, download_link):
            assert image_path == __file__, "Expecting given mock `image_path` to match '{}'".format(__file__)
            return "no_upload"

        cloud_notifier = CloudNotifier(fake_post, fake_upload)
        cloud_notifier.notify(job, __file__, n_iterations=-1)

        expected_payload = {'query': 'mutation NotifyJobEvent($in: JobScalarChangesWithImageInput!)'
                                     ' {notifyJobScalarChangesWithImage(input: $in)}'}
        # Verify query structure
        assert 'query' in posted_payload, "Payload is expected to contain the key 'query'"
        assert posted_payload['query'] == expected_payload['query'], "GraphQL queries should be identical"
        assert 'variables' in posted_payload, "Payload is expected to contain the key 'variables'"
        assert 'in' in posted_payload['variables'], "'variables' dictionary is expected to contain a key called 'in'"
        # Verify empty imageUrl
        variables = posted_payload['variables']['in']
        assert 'imageUrl' in variables, "'in' dictionary is expected to contain a key called 'imageUrl'"
        assert variables['imageUrl'] == "no_upload", "`imageUrl` value is expected to " \
                                                     "contain hard-coded value `no_upload`"


@pytest.mark.usefixtures("cleanup")
class TestNotifierHistory:
    # General Notifier Tests
    def test_notifier_history(self):  # pylint:disable=unused-argument,redefined-outer-name
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
        assert len(notifications) == 1, "Expecting a single notification at this point (JobStart)"
        assert notifications[0].type == NotificationType.JOB_START, "Notification type should be Job Start"
        assert notifications[0].status == NotificationStatus.SUCCESS, "Notification is expected to succeed " \
                                                                      "with Mock `post`"

        last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
        assert last_notification is not None, "There was a single notification, we expect a concrete value"
        assert last_notification.type == NotificationType.JOB_START, "Notification type should be Job Start"
        assert last_notification.status == NotificationStatus.SUCCESS, "Notification was expected to succeed"

        should_raise = True
        cloud_notifier.notify_job_end(job)

        # Validate history for notify_job_end
        notifications = cloud_notifier.get_notification_history(job.id)[cloud_notifier.name]
        assert len(notifications) == 2, "Expecting two notification at this point (JobStart, JobEnd)"
        assert notifications[1].type == NotificationType.JOB_END, "Second notification type should be Job End"
        assert notifications[1].status == NotificationStatus.FAILED, "Notification has failed here due to set flag"

        last_notification = cloud_notifier.get_last_notification_status(job.id)[cloud_notifier.name]
        assert last_notification is not None, "We expect a concrete value after any event has happened"
        assert last_notification.type == NotificationType.JOB_END, "Last notification type was Job End"
        assert last_notification.status == NotificationStatus.FAILED, "Last notification has failed to due to set flag"


@pytest.mark.usefixtures("cleanup")
class TestNotifierCollection:
    # NotifierCollection Tests
    def test_notifier_collection_notifiers_init(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests init with notifiers"""
        assert_msg1 = "Both created notifiers should be found in the `_notifiers` list"
        cloud_notifier = CloudNotifier(_empty_post, _empty_upload)
        logging_notifier = LoggingNotifier()

        # Proper init
        collection = NotifierCollection(*[cloud_notifier, logging_notifier])
        assert len(collection._notifiers) == 2, "There are two registered notifiers in the collection"
        assert cloud_notifier in collection._notifiers and logging_notifier in collection._notifiers, assert_msg1

        # Empty init
        collection = NotifierCollection()
        assert len(collection._notifiers) == 0, "NotifierCollection was instantiated without any notifiers! " \
                                                "How come there are any registered?"

        # Bad init
        collection = NotifierCollection(*[cloud_notifier, cloud_notifier])
        assert len(collection._notifiers) == 1, "NotifierCollection was instantiated with the same object multiple" \
                                                "times, but only one unique instance of an object can be stored."

    def test_notifier_collection_registering_notifiers(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the register_notifier method"""
        cloud_notifier = CloudNotifier(_empty_post, _empty_upload)
        cloud_notifier2 = CloudNotifier(_empty_post, _empty_upload, name="smeagol")
        collection = NotifierCollection()

        # Sanity check
        assert len(collection._notifiers) == 0, "Sanity check - empty NotifierCollection"

        # Adding
        assert collection.register_notifier(cloud_notifier), "Adding a new notifier should return True"
        assert len(collection._notifiers) == 1, "A single notifier was added to the collection!"

        # Adding again?
        assert not collection.register_notifier(cloud_notifier), "Trying to add an already-added notifier should " \
                                                                 "return False and not add the notifier to the list"

        # Adding same class, different name
        assert collection.register_notifier(cloud_notifier2), "Adding a new notifier of the same class should succeed"
        assert len(collection._notifiers) == 2, "There are now two registered notifiers!"

    def test_notifier_collection_notifications(self):  # pylint:disable=unused-argument,redefined-outer-name
        """Tests the job notifications are sent to all registered notifiers, along with history management"""
        assert_msg1 = "Last notification type was JobUpdate"
        assert_msg2 = "CloudNotifier is expected to succeed with a fake `post` method"
        assert_msg3 = "LoggingNotifier is expected to fail with non-existing output path"
        assert_msg4 = "History for CloudNotifier from NotifierCollection should match CloudNotifier internal history"
        assert_msg5 = "History for LoggingNotifier from NotifierCollection " \
                      "should match LoggingNotifier internal history"
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
            assert cloud_counter == logging_counter == 1, "A single event (JobStart) should be sent to both notifiers"

            # Test with notify_job_end
            collection.notify_job_end(job)
            assert cloud_counter == logging_counter == 2, "Two events have now been registered to both notifiers " \
                                                          "(JobStart, JobEnd)"

            # Test with notify
            collection.notify(job, "", -1)
            # Validate `notify` via job_history
            last_notification = collection.get_last_notification_status(job.id)
            assert len(last_notification) == 2, "There are two notifiers, so we expect two keys " \
                                                "in the last notification"
            assert cloud_notifier.name in last_notification, "CloudNotifier name '{}' should be a " \
                                                             "key".format(cloud_notifier.name)
            assert logging_notifier.name in last_notification, "LoggingNotifier name '{}' should be a " \
                                                               "key".format(logging_notifier.name)
            assert last_notification[cloud_notifier.name].type == NotificationType.JOB_UPDATE, assert_msg1
            assert last_notification[logging_notifier.name].type == NotificationType.JOB_UPDATE, assert_msg1
            # Cloud notification is expected to be successful as we emulate the upload and posting process
            assert last_notification[cloud_notifier.name].status == NotificationStatus.SUCCESS, assert_msg2
            # Logging notification is expected to fail as the target directory does not exist
            assert last_notification[logging_notifier.name].status == NotificationStatus.FAILED, assert_msg3

            # Test history
            history = collection.get_notification_history(job.id)
            assert len(history) == 2, "The entire history should have two keys - one for each notifier"
            assert cloud_notifier.name in last_notification, "CloudNotifier name '{}' should be a " \
                                                             "key".format(cloud_notifier.name)
            assert logging_notifier.name in last_notification, "LoggingNotifier name '{}' should be a " \
                                                               "key".format(logging_notifier.name)
            cloud_history = history[cloud_notifier.name]
            logging_history = history[logging_notifier.name]
            assert cloud_history == cloud_notifier.get_notification_history(job.id)[cloud_notifier.name], assert_msg4
            assert logging_history == logging_notifier.get_notification_history(job.id)[logging_notifier.name], assert_msg5
