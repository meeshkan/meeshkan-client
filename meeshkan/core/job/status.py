from enum import Enum

# Expose JobStatus to upper level (make `from meeshkan.core.job import JobStatus` work, as well as
#     `from meeshkan.core.job.status import JobStatus`)
__all__ = ["JobStatus"]

class JobStatus(Enum):
    CREATED = 0  # New job
    QUEUED = 1  # Added to QueueProcessor
    RUNNING = 2  # Currently running
    FINISHED = 3  # Finished task successfully
    CANCELED = 4  # Aborted outside of scheduler (e.g. user used `kill -9 ...`)
    FAILED = 5  # Failed due to some errors
    CANCELLED_BY_USER = 10  # Marked cancelled by service

    @property
    def is_launched(self):
        """Returns whether or not the job has been running at all"""
        return self == JobStatus.RUNNING or self.is_processed

    @property
    def is_running(self):
        """Returns whether or not the job is currently running"""
        return self == JobStatus.RUNNING

    @property
    def is_processed(self):
        return self in [JobStatus.CANCELED, JobStatus.FAILED, JobStatus.FINISHED]

    @property
    def stale(self):
        return self == JobStatus.CANCELLED_BY_USER
