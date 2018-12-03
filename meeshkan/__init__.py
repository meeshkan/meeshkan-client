from .__version__ import __version__  # Conform to PEP-0396

from .core import *  # pylint: disable=wildcard-import
from . import core
from . import exceptions

# Only make the following available by default
__all__ = ["__version__", "exceptions", "report_scalar", "add_condition", "config"]

del core  # Clean-up (make `meeshkan.core` unavailable)


def report_scalar(val_name, value, *vals) -> bool:
    """Reports scalars to the meeshkan service API

    :param val_name: The name of the scalar to report
    :param value: The value of the scalar
    :param vals: any additional value_name, value to add.
    :param condition: A callable that accepts all scalars registered in this statement, and return True or False,
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


def add_condition(*vals, condition, only_reported=False):
    """Adds a condition to send notification for given values when condition holds

    :param vals: A list of value names to monitor
    :param condition: A callable accepting as many arguments as listed values, and returns whether the notification
        condition has been met.
    :param only_reported: Flag whether or not to report all scalars in a job, or just the ones relevant to the condition
        (False by default -> reports all scalars in the job)
    """
    import os  # pylint: disable=redefined-outer-name
    import dill  # pylint: disable=redefined-outer-name
    from .core.service import Service  # pylint: disable=redefined-outer-name

    if not vals:
        raise RuntimeError("No arguments given for condition!")

    pid = os.getpid()
    with Service().api as proxy:
        # Uses old encoding, see https://stackoverflow.com/a/27527728/4133131
        proxy.add_condition(pid, dill.dumps(condition).decode('cp437'), only_reported, *vals)
