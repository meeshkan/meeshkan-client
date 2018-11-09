class UnauthorizedRequestException(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        if len(message) > 0:
            message = "\n{message}".format(message=message)
        self.message = "Unauthorized. Check your credentials.{message}".format(message=message)

class OldVersionException(Exception):
    """Raised when there exists a new version of meeshkan."""
    def __init__(self):
        self.message = "Update exists - please update meeshkan first."

