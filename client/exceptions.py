class UnauthorizedRequestError(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        if len(message) > 0:
            message = f"\n{message}"
        self.message = f"Unauthorized. Check your credentials.{message}"

