class UnauthorizedRequestException(Exception):
    """Raised when cloud server responds with 401."""
    def __init__(self, message=""):
        super().__init__()
        if message:
            message = "\n{message}".format(message=message)
        self.message = "Unauthenticated. Please configure your credentials by running \"meeshkan setup\".{message}"\
            .format(message=message)


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


class SageMakerNotAvailableException(Exception):
    def __init__(self, message=None):
        error_message = message or "Unable to access SageMaker training jobs. " \
                                   "Please check your AWS credential chain and try again."
        super().__init__(error_message)


class DeferredImportException:

    def __init__(self, exception):
        self.exception = exception

    def __getattr__(self, name):
        raise self.exception


class AgentNotAvailableException(Exception):
    def __index__(self):
        super().__init__("Start the agent first.")


class MismatchingIPythonKernelException(Exception):
    def __init__(self, found_kernel_type, expected_kernel_type):
        super().__init__("Found an IPython kernel, but it doesn't match the expected type (found {found},"
                         "expected {expected}".format(found=found_kernel_type, expected=expected_kernel_type))


class InvalidTypeForFunctionSubmission(Exception):
    def __init__(self, typename):
        super().__init__("Encountered non-function '{typename}' when submitting a function.".format(typename=typename))
