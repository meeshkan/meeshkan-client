import os

from ..core.service import Service
from ..core.serializer import Serializer

__all__ = ["add_condition"]


def add_condition(*vals, condition, only_reported=False):
    """
    Adds a condition to send notification when scalars fulfill a condition. Requires Meeshkan agent
    to be running and aware of the job context as for :func:`meeshkan.report_scalar`.

    Example::

        # Add a condition to notify when training loss is less than 0.8
        meeshkan.add_condition("train_loss", lambda v: v < 0.8)

        # Add another condition to notify when `val_loss` and `val_acc` are smaller and greater
        # than given values, respectively
        meeshkan.add_condition("val_loss", "val_acc", lambda loss, acc: loss < 0.5 and acc > 0.95)

        for epoch in range(EPOCHS):
            # Compute `train_loss`
            train_loss = ...
            # Report the value to the agent.
            # If the added condition is fulfilled, notification is sent.
            meeshkan.report_scalar("train_loss", train_loss)

            # Report validation results
            if epoch % VALIDATION_INTERVAL == 0:
                val_loss = ...
                val_acc = ...
                meeshkan.report_scalar("val_loss", val_loss, "val_acc", val_acc)

    :param vals: List of scalar names to include in the condition definition.
    :param condition: A callable accepting as many arguments as listed values and returning boolean.
    :param only_reported: Report all scalars in a job if True, only report the ones \
    relevant to the condition if False. Defaults to False.
    """
    if not vals:
        raise TypeError("No arguments given for condition!")

    pid = os.getpid()
    with Service.api() as proxy:
        proxy.add_condition(pid, Serializer.serialize(condition), only_reported, *vals)
