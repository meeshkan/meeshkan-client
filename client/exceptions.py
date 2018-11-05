

class Unauthorized(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self):
        self.message = "Unauthorized. Check your credentials."
        super(Unauthorized, self).__init__(self.message)
