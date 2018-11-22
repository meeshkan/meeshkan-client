from .__version__ import __version__  # Conform to PEP-0396
from .__types__ import Payload, Token, HistoryByScalar  # Bring types to front

from .core import *  # pylint: disable=wildcard-import
from . import core
from . import exceptions

# Only make the following available by default
__all__ = ["__version__", "exceptions", "Payload", "Token", "HistoryByScalar", "report_scalar"]
__all__ += core.__all__

del core  # Clean-up (make `meeshkan.core` unavailable)

def report_scalar(val_name, value):
    """Reports a scalar to the meeshkan service API"""
    import os  # pylint: disable=redefined-outer-name
    with Service().api as proxy:
        return proxy.report_scalar(os.getpid(), val_name, value)
