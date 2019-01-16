import os
from ..core.service import Service
from ..exceptions import JobNotFoundException

__all__ = ["report_scalar"]


def report_scalar(val_name, value, *vals) -> bool:
    """Reports scalars to the meeshkan service API

    :param val_name: The name of the scalar to report
    :param value: The value of the scalar
    :param vals: any additional value_name, value to add.
    :param condition: A callable that accepts all scalars registered in this statement, and return True or False,
        indicating whether a notification is required.
    """
    if len(vals) % 2:  # Invalid number of additional scalar arguments given
        raise RuntimeError("Invalid number of arguments given - did you forget a name/value?")

    pid = os.getpid()
    with Service().api as proxy:
        try:
            proxy.report_scalar(pid, val_name, value)
            for name, val in zip(vals[::2], vals[1::2]):
                proxy.report_scalar(pid, name, val)
        except JobNotFoundException:
            return False
    return True
