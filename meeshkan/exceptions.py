class UnauthorizedRequestException(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        super().__init__()
        if message:
            message = "\n{message}".format(message=message)
        self.message = "Unauthorized. Check your credentials.{message}".format(message=message)


class OldVersionException(Exception):
    """Raised when there exists a new version of meeshkan."""
    def __init__(self):
        super().__init__()
        self.message = "Update exists - please update meeshkan first."

class JobNotFoundException(Exception):
    """Raised when looking for a job via some lookup in scheduler, and not finding it."""
    def __init__(self, job_id=""):
        super().__init__()
        self.message = "Couldn't find given job ID {id}.".format(id=job_id)

class TrackedScalarNotFoundException(Exception):
    """Raised when looking for a scalar that does not exist"""
    def __init__(self, name=""):
        super().__init__()
        self.message = "Couldn't find history for requested scalar '{name}'.".format(name=name)

class MissingNotificationKeywordArgument(Exception):
    """Raised when attempting to dispatch a notification with missing keyword arguments"""
    def __init__(self, notification, keyword):
        super().__init__()
        self.message = "Missing keyword '{kw}' for '{notification}' notification.".format(kw=keyword,
                                                                                          notification=notification)
