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
