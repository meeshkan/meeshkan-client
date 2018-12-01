from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from . import exceptions

# Only make the following available by default
__all__ = ["__version__", "exceptions", "report_scalar", "config"]

del core  # Clean-up (make `meeshkan.core` unavailable)


def report_scalar(val_name, value, *vals, cond=None) -> bool:
    """Reports scalars to the meeshkan service API

    :param val_name: The name of the scalar to report
    :param value: The value of the scalar
    :param vals: any additional value_name, value to add.
    :param cond: A callable that accepts all scalars registered in this statement, and return True or False,
        indicating whether a notification is required.
    """
    # These imports are defined locally to prevent them from being visible in `help(meeshkan)` etc
    import os  # pylint: disable=redefined-outer-name
    from .core.service import Service  # pylint: disable=redefined-outer-name

    if len(vals) % 2:  # Invalid number of additional scalar arguments given
        raise RuntimeError("Invalid number of arguments given - did you forget a name/value?")

    pid = os.getpid()
    with Service().api as proxy:
        try:
            proxy.report_scalar(pid, val_name, value)
            for name, val in zip(vals[::2], vals[1::2]):
                proxy.report_scalar(pid, name, val)
        except exceptions.JobNotFoundException:
            return False
    return True


def condition(*vals, cond):
    """Sets a condition to send notification for given values

    :param vals: A list of value names to monitor
    :param cond: A callable accepting as many arguments as listed values, and returns whether the notification
        condition has been met.
    """
    import os  # pylint: disable=redefined-outer-name
    import dill
    from .core.service import Service  # pylint: disable=redefined-outer-name

    if not vals:
        raise RuntimeError("No arguments given for condition!")

    pid = os.getpid()
    # TODO - fill in the gap
    # TODO - probably includes moving Scalar History to Job, querying from the Job itself, etc.
    with Service().api as proxy:
        # Uses old encoding, see https://stackoverflow.com/a/27527728/4133131
        proxy.condition(pid, dill.dumps(cond).decode('cp437'), *vals)
