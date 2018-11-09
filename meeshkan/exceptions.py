class UnauthorizedRequestException(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        super().__init__()
        if message:
            message = f"\n{message}"
        self.message = f"Unauthorized. Check your credentials.{message}"


class OldVersionException(Exception):
    """Raised when there exists a new version of meeshkan."""
    def __init__(self):
        super().__init__()
        self.message = "Update exists - please update meeshkan first."
