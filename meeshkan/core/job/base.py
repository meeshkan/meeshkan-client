"""Contains the base classes for the Job API, as well as some other _basic functionality_ classes"""

import logging
from typing import Callable, Optional
import uuid
import datetime

from ..tracker import TrackerBase, TrackerCondition
from .status import JobStatus

LOGGER = logging.getLogger(__name__)

# Expose only BaseJob class
__all__ = ["BaseJob"]


class Trackable:
    """
    Base class for all trackable jobs, run by Meeshkan, SageMaker or some other means
    """
    def __init__(self, scalar_history: Optional[TrackerBase] = None):
        super().__init__()
        self.scalar_history = scalar_history or TrackerBase()  # type: TrackerBase

    def add_scalar_to_history(self, scalar_name, scalar_value) -> Optional[TrackerCondition]:
        return self.scalar_history.add_tracked(scalar_name, scalar_value)

    def add_condition(self, *val_names: str, condition: Callable[[float], bool], only_relevant: bool):
        self.scalar_history.add_condition(*val_names, condition=condition, only_relevant=only_relevant)

    def get_updates(self, *names, plot, latest):
        """Get latest updates for tracked scalar values. If plot == True, will also plot all tracked scalars.
        If latest == True, returns only latest updates, otherwise returns entire history.
        """
        # Delegate to HistoryTracker
        return self.scalar_history.get_updates(*names, plot=plot, latest=latest)


class Stoppable:
    def terminate(self):
        raise NotImplementedError


class BaseJob(Stoppable, Trackable):
    """
    Base class for all jobs handled by Meeshkan agent
    """
    DEF_POLLING_INTERVAL = 3600.0  # Default is notifications every hour.

    def __init__(self, status: JobStatus, job_uuid: Optional[uuid.UUID] = None, job_number: Optional[int] = None,
                 name: Optional[str] = None, poll_interval: Optional[float] = None):
        super().__init__()
        self.status = status
        # pylint: disable=invalid-name
        self.id = job_uuid or uuid.uuid4()  # type: uuid.UUID
        self.number = job_number  # Human-readable integer ID
        self.poll_time = poll_interval or BaseJob.DEF_POLLING_INTERVAL  # type: float
        self.created = datetime.datetime.utcnow()
        self.name = name or "Job #{number}".format(number=self.number)

    def terminate(self):
        raise NotImplementedError
