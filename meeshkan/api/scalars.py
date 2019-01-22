import os
from ..core.service import Service
from ..exceptions import JobNotFoundException

__all__ = ["report_scalar"]


def report_scalar(val_name: str, value: float, *vals) -> bool:
    """
    Reports scalars to the Meeshkan agent. Reported scalars are included in the sent notifications.

    Requires Meeshkan agent to be running and aware of the
    job context. The job context can be defined in multiple ways:

        1. By submitting the script or notebook for execution to the agent with ``meeshkan submit``.
        2. By decorating a function with :func:`meeshkan.as_blocking_job`
        3. By using the job context manager :func:`meeshkan.create_blocking_job`

    Example of ``train.py`` script submitted with ``meeshkan submit --name my-job train.py``::

        import meeshkan

        EPOCHS = 10

        for epoch in range(EPOCHS):
            # Compute loss
            loss = ...
            # Report loss to the Meeshkan agent
            meeshkan.report_scalar("loss", loss)

    :param val_name: The name of the scalar to report
    :param value: The value of the scalar
    :param vals: Any additional (val_name, value) pairs to add.
    :return bool: True if job was found, False if not.
    """
    if len(vals) % 2:  # Invalid number of additional scalar arguments given
        raise RuntimeError("Invalid number of arguments given - did you forget a name/value?")

    pid = os.getpid()
    with Service.api() as proxy:
        try:
            proxy.report_scalar(pid, val_name, value)
            for name, val in zip(vals[::2], vals[1::2]):
                proxy.report_scalar(pid, name, val)
        except JobNotFoundException:
            return False
    return True
