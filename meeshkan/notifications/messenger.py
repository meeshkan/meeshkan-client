from typing import List, Dict, Tuple, Callable
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

NotificationWithStatus = Tuple[NotificationType, NotificationStatus]
LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]

class Messenger(object):
    def __init__(self):
        self._listeners = list()  # type: List[Notifier]
        # Value is a dictionary of lists with notifier type as key and tuples of notification type and status as values
        self._notification_history_by_job = dict()  # type: Dict[uuid.UUID, Dict[str, List[NotificationWithStatus]]]

    # Methods to handle job notification history

    def get_notification_history(self, job_id: uuid.UUID) -> Dict[str, List[NotificationWithStatus]]:
        """Returns the notification history for """
        if job_id not in self._notification_history_by_job:
            raise JobNotFoundException
        return self._notification_history_by_job[job_id]

    def get_last_notification_status(self, job_id: uuid.UUID) -> Dict[str, NotificationWithStatus]:
        if job_id not in self._notification_history_by_job:
            raise JobNotFoundException
        last_notifications = dict()
        for notifier_type, notification_list in self._notification_history_by_job[job_id].items():
            last_notifications[notifier_type] = notification_list[-1]
        return last_notifications

    def _add_notification_history(self, job_id: uuid.UUID, notifier: Notifier, notification_type: NotificationType,
                                  notification_status: NotificationStatus):
        name = notifier.__class__.__name__
        result = (notification_type, notification_status)
        self._notification_history_by_job.setdefault(job_id, dict()).setdefault(name, list()).append(result)

    # Methods to handle listeners

    def register_listener(self, listener: Notifier):
        self._listeners.append(listener)

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
        for notifier in self._listeners:
            try:
                callback(notifier)
                self._add_notification_history(job_id, notifier, notification_type, NotificationStatus.SUCCESS)
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Notifier %s failed", notifier.__class__.__name__)
                self._add_notification_history(job_id, notifier, notification_type, NotificationStatus.FAILED)
                result = False

        return result
