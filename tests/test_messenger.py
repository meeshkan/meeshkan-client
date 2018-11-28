# import pytest
#
# from meeshkan.notifications.notifiers import Notifier
# from meeshkan.notifications.messenger import Messenger, NotificationType, NotificationStatus
# from meeshkan.exceptions import MissingNotificationKeywordArgument
# from meeshkan.core.job import Executable, Job
#
#
# def _get_job():
#     return Job(Executable(), job_number=0)
#
#
# class MockNotifier(Notifier):
#     def __init__(self):
#         super().__init__()
#         self.started_jobs = list()
#         self.notified_jobs = list()
#         self.finished_jobs = list()
#
#     def notify_job_start(self, job: Job):
#         self.started_jobs.append({'job': job})
#
#     def notify_job_end(self, job: Job):
#         self.finished_jobs.append({'job': job})
#
#     def notify(self, job: Job, image_url: str, n_iterations: int = -1, iterations_unit: str = "iterations") -> None:
#         self.notified_jobs.append({'job': job})
#
#
# def test_messenger_notifiers():
#     """Tests addition of notifiers via init and register_notifier methods"""
#     notifier = MockNotifier()
#     messenger = Messenger()
#     assert len(messenger._notifiers) == 0
#     assert messenger.register_notifier(notifier)  # Should be True
#     assert len(messenger._notifiers) == 1
#     assert not messenger.register_notifier(notifier)  # Should be False
#     assert len(messenger._notifiers) == 1  # Should not be added again
#
#     messenger = Messenger(*[notifier])
#     assert len(messenger._notifiers) == 1
#
# def test_messenger_notification_history():
#     """Verifies the _add_notification_history method"""
#     notifier = MockNotifier()
#     class_name = notifier.__class__.__name__
#     messenger = Messenger(*[notifier])
#     job = _get_job()
#
#     assert len(messenger._notification_history_by_job) == 0
#
#     messenger._add_notification_history(job.id, {NotificationType.JOB_START: {class_name: NotificationStatus.SUCCESS}})
#
#     assert len(messenger._notification_history_by_job) == 1  # Only one job registered
#     assert len(messenger._notification_history_by_job[job.id]) == 1  # Only one notification registered for that job
#     assert len(messenger._notification_history_by_job[job.id][-1]) == 1  # Only one notifier for that notification
#     notification = list(messenger._notification_history_by_job[job.id][-1].values())[0]
#     assert list(notification.values())[0] == NotificationStatus.SUCCESS
#
#     # Same but with `Messenger`s methods
#     notification_type, notifications_dictionary = messenger.get_last_notification_status(job.id)
#     assert notification_type ==NotificationType.JOB_START
#     assert len(notifications_dictionary) == 1
#     assert class_name in notifications_dictionary
#     assert notifications_dictionary[class_name] == NotificationStatus.SUCCESS
#
#     notification_list = messenger.get_notification_history(job.id)
#     assert len(notification_list) == 1
#     assert notification_list[0] == {NotificationType.JOB_START: {class_name: NotificationStatus.SUCCESS}}
#
# def test_messenger_internal_loop():
#     """Tests the `_internal_loop` method"""
#     notifier = MockNotifier()
#     messenger = Messenger(*[notifier])
#     job = _get_job()
#
#     def successful_callback(callback_notifier):
#         callback_notifier.notify_job_start(job)
#
#     def bad_callback(callback_notifier):
#         raise RuntimeError("Boom!")
#
#     assert messenger._internal_notifier_loop(job.id, NotificationType.JOB_START, successful_callback)
#     assert len(notifier.started_jobs) == 1
#     assert not messenger._internal_notifier_loop(job.id, NotificationType.JOB_START, bad_callback)
#     assert len(notifier.started_jobs) == 1
#     assert notifier.started_jobs[0]['job'] == job
#
# def test_messenger_dispatch():
#     """Tests the `dispatch` method in Messenger"""
#     notifier = MockNotifier()
#     messenger = Messenger(*[notifier])
#     job = _get_job()
#
#     messenger.dispatch(NotificationType.JOB_START, job)
#     assert len(notifier.started_jobs) == 1
#     assert notifier.started_jobs[0]['job'] == job
#
#     messenger.dispatch(NotificationType.JOB_END, job)
#     assert len(notifier.finished_jobs) == 1
#     assert notifier.finished_jobs[0]['job'] == job
#
#     messenger.dispatch(NotificationType.JOB_UPDATE, job, **{'image_path': None, 'n_iterations': -1})
#     assert len(notifier.notified_jobs) == 1
#     assert notifier.notified_jobs[0]['job'] == job
#
#     with pytest.raises(MissingNotificationKeywordArgument):
#         messenger.dispatch(NotificationType.JOB_UPDATE, job, **{'n_iterations': -1})
#
#