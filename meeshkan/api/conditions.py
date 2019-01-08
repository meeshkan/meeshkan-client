import os
import dill

from ..core.service import Service

__all__ = ["add_condition"]


def add_condition(*vals, condition, only_reported=False):
    """Adds a condition to send notification for given values when condition holds

    :param vals: A list of value names to monitor
    :param condition: A callable accepting as many arguments as listed values, and returns whether the notification
        condition has been met.
    :param only_reported: Flag whether or not to report all scalars in a job, or just the ones relevant to the condition
        (False by default -> reports all scalars in the job)
    """
    if not vals:
        raise RuntimeError("No arguments given for condition!")

    pid = os.getpid()
    with Service().api as proxy:
        # Uses old encoding, see https://stackoverflow.com/a/27527728/4133131
        # recurse==True also packs relevant modules etc and imports if needed and declared in a different module...
        proxy.add_condition(pid, dill.dumps(condition, recurse=True).decode('cp437'), only_reported, *vals)
