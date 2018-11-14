from .__version__ import __version__  # Conform to PEP-0396
from .__types__ import Payload, Token, History  # Bring types to front
__all__ = ["cloud", "oauth", "exceptions", "job", "notifiers", "scheduler", "service", "api", "config", "logger",
           "tracker"]

def report_scalar(val_name, value):
    """Reports a scalar to the meeshkan service API"""
    import Pyro4  # Hide these modules from outside world
    import os
    import meeshkan.service
    with Pyro4.Proxy(meeshkan.service.Service().uri) as proxy:
        return proxy.report_scalar(os.getpid(), val_name, value)

def get_api():
    import Pyro4
    import meeshkan.service
    return Pyro4.Proxy(meeshkan.service.Service().uri)
