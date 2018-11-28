from typing import List, Dict, Tuple, Callable, Union
import logging
from enum import Enum, auto
import uuid

from .notifiers import Notifier
from ..core.job import Job  # TODO: This class should be unaware of 'jobs', once cloud's notification gql is generic
from ..exceptions import JobNotFoundException, MissingNotificationKeywordArgument

class NotificationStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()

class NotificationType(Enum):
    JOB_START = auto()
    JOB_END = auto()
    JOB_UPDATE = auto()

NotificationWithStatus = Dict[NotificationType, Dict[str, NotificationStatus]]
NotificationWithStatusTuple = Tuple[NotificationType, Dict[str, NotificationStatus]]
LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]

class Messenger(object):
    def __init__(self, *args):
        """Creates a messenger object, responsible of orchestrating notifiers and notifications.
        Allows only one notifier of each class.  # TODO do we want this more relaxed and allow naming notifiers?

        :param notifiers: Optional list of notifiers to initialize the messenger with
        """
        self._notifiers = list()  # type: List[Notifier]
        # Value is a list of dictionaries (notifications) with dictionaries as values (notifier and status)
        self._notification_history_by_job = dict()  # type: Dict[uuid.UUID, List[NotificationWithStatus]]
        for notifier in args:
            self.register_notifier(notifier)

    # Methods to handle job notification history

    def get_notification_history(self, job_id: uuid.UUID) -> List[NotificationWithStatus]:
        """Returns the notification history for given job"""
        if job_id not in self._notification_history_by_job:
            raise JobNotFoundException
        return self._notification_history_by_job[job_id]

    def get_last_notification_status(self, job_id: uuid.UUID) -> Union[NotificationWithStatusTuple, Tuple[None, None]]:
        """Returns a tuple of NotificationType and dictionary with notifiers class as keys and status as values.
        If no notifications exist for the job, return a tuple of Nones.
        If the job does not exist, raises a JobNotFound exception.
        """
        if job_id not in self._notification_history_by_job:
            raise JobNotFoundException
        job_notifications = self._notification_history_by_job[job_id]
        if job_notifications:
            return Messenger._extract_from_notification(job_notifications[-1])
        return None, None

    @staticmethod
    def _extract_from_notification(notification: NotificationWithStatus) -> NotificationWithStatusTuple:
        """As each NotificationWithStatus is a single key-value pair, this breaks it down to a tuple"""
        # Each item in the list is a dictionary with a single item, so .items() returns a list of length 1
        key, value = next(iter(notification.items()))
        LOGGER.debug("Key-value: %s %s", key, value)
        return key, value

    def _add_notification_history(self, job_id: uuid.UUID, notification_result: NotificationWithStatus):
        self._notification_history_by_job.setdefault(job_id, list()).append(notification_result)

    # Methods to handle listeners

    def register_notifier(self, new_notifier: Notifier) -> bool:
        """Registers a new notifier. Fails if a notifier of that class is already registered. """
        # Verify new_notifier does not exist in the class yet
        for notifier in self._notifiers:
            if notifier.__class__.__name__ == new_notifier.__class__.__name__:
                LOGGER.debug("Notifier of type %s already exists", new_notifier.__class__.__name__)
                return False
        LOGGER.debug("Registering notifier: %s", new_notifier.__class__.__name__)
        self._notifiers.append(new_notifier)
        return True

    # Methods to handle notifications

    def dispatch(self, notification_type: NotificationType, job: Job, **kwargs) -> bool:
        """Sends the relevant notification to all listeners; uses specific keywords for each notification.
        Consider this a "factory" for notifications.

        :param notification_type: Type of notification to send from NotificationType
        :param job: Job for which to dispatch information.  # TODO remove dependancy on Job class in the future?
        :param kwargs: Keyword arguments for the notification.
            JOB_START: Requires no further arguments
            JOB_END: Requires no further arguments
            JOB_UPDATE: Requires an 'image_path' keyword with str argument
                        Requires 'n_iterations' keyword with int argument
                        Optional 'unit' keyword with str argument (unit of iterations)
        """
        # Create callback and verify arguments

        if notification_type == NotificationType.JOB_START:
            def callback(notifier):
                notifier.notify_job_start(job)

        elif notification_type == NotificationType.JOB_END:
            def callback(notifier):
                notifier.notify_job_end(job)

        elif notification_type == NotificationType.JOB_UPDATE:
            mandatory_kwargs = ['image_path', 'n_iterations']
            for keyword in mandatory_kwargs:
                if keyword not in kwargs:
                    LOGGER.error("Missing keyword '%s' for notification '%s'", keyword, notification_type)
                    raise MissingNotificationKeywordArgument(notification_type.JOB_UPDATE, keyword)

            image_path = kwargs['image_path']
            n_iterations = kwargs['n_iterations']
            iterations_unit = kwargs.get('unit', 'iterations')

            def callback(notifier):
                notifier.notify(job, image_path, n_iterations, iterations_unit)

        else:
            LOGGER.error("Unrecognized notification type %s", notification_type)
            raise RuntimeError("Unrecognized notification type {type}".format(type=notification_type))

        return self._internal_notifier_loop(job.id, notification_type, callback)


    def _internal_notifier_loop(self, job_id: uuid.UUID, notification_type: NotificationType,
                                callback: Callable[[Notifier], None]):
        """Goes over all the notifiers and calls `callback` on each; updating the notification history throughout."""
        result = True
        notification_result = dict()
        for notifier in self._notifiers:
            try:
                callback(notifier)
                notification_result[notifier.__class__.__name__] = NotificationStatus.SUCCESS
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Notifier %s failed", notifier.__class__.__name__)
                notification_result[notifier.__class__.__name__] = NotificationStatus.FAILED
                result = False
        self._add_notification_history(job_id, {notification_type: notification_result})
        return result
