import time
from typing import Tuple
from enum import Enum, auto


class NotificationStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()


class NotificationType(Enum):
    JOB_START = auto()
    JOB_END = auto()
    JOB_UPDATE = auto()


class NotificationWithStatusTime:
    """Class to hold a notification type, timestamp and status"""
    def __init__(self, notification_type: NotificationType, status: NotificationStatus):
        self.time = time.strftime(time.strftime("%D %H:%M:%S"))
        self.type = notification_type
        self.status = status
