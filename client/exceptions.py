class Unauthorized(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        if len(message) > 0:
            message = "\n{message}".format(message=message)
        self.message = "Unauthorized. Check your credentials.{message}".format(message=message)

