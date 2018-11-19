from .__version__ import __version__  # Conform to PEP-0396
from .__types__ import Payload, Token, HistoryByScalar  # Bring types to front
__all__ = ["cloud", "oauth", "exceptions", "job", "notifiers", "scheduler", "service", "tasks",
           "api", "config", "logger", "tracker"]

def report_scalar(val_name, value):
    """Reports a scalar to the meeshkan service API"""
    import os
    import meeshkan.service
    with meeshkan.service.Service().api as proxy:
        return proxy.report_scalar(os.getpid(), val_name, value)
