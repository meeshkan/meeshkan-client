from typing import Tuple
from enum import Enum, auto

class NotificationStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()

class NotificationType(Enum):
    JOB_START = auto()
    JOB_END = auto()
    JOB_UPDATE = auto()


# Keys are class names of different Notifiers
NotificationWithStatus = Tuple[NotificationType, NotificationStatus]
# Adds a string to the above tuple to allow for additional identifier (e.g. time/date)
NotificationWithStatusTime = Tuple[str, NotificationType, NotificationStatus]
