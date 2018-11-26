from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from . import exceptions

# Only make the following available by default
__all__ = ["__version__", "exceptions", "report_scalar", "config"]

del core  # Clean-up (make `meeshkan.core` unavailable)


def report_scalar(val_name, value):
    """Reports a scalar to the meeshkan service API

    :param val_name: The name of the scalar to report
    :param value: The value of the scalar
    """
    # These imports are defined locally to prevent them from being visible in `help(meeshkan)` etc
    import os  # pylint: disable=redefined-outer-name
    from .core.service import Service  # pylint: disable=redefined-outer-name
    with Service().api as proxy:
        return proxy.report_scalar(os.getpid(), val_name, value)
