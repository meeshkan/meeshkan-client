"""Module to enable remote querying of python processeses from outside the current process."""
import os
from typing import Union, List, Dict, Tuple, Optional, Callable, Any
from pathlib import Path
import time
import uuid
import tempfile
import logging
import asyncio
import inspect

from ..__types__ import HistoryByScalar, ScalarIndexPairing
from ..exceptions import TrackedScalarNotFoundException

TF_EXISTS = True
try:
    import tensorboard.backend.event_processing.event_accumulator as tfproto
except ModuleNotFoundError:
    TF_EXISTS = False  # Silently fail

LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class TrackingPoller:
    def __init__(self, notify_function: Callable[[uuid.UUID], Any]):
        self._notify = notify_function

    async def poll(self, job_id, poll_time: float):
        """Asynchronous polling function for scalars in given job"""
        LOGGER.debug("Starting job tracking for job %s", job_id)
        sleep_time = poll_time
        try:
            while True:
                await asyncio.sleep(sleep_time)  # Let other tasks run meanwhile
                self._notify(job_id)  # Synchronously notify of changes.
        except asyncio.CancelledError:
            LOGGER.debug("Job tracking cancelled for job %s", job_id)


class TrackerCondition:
    DEF_COOLDOWN_PERIOD = 30  # 30 seconds interval default cooldown period
    def __init__(self, *value_names: str, condition: Callable[[float], bool], title: str,
                 default_value=1, cooldown_period: int = None, only_relevant: bool = False):
        """
        Initializes a new condition for tracking
        :param value_names: List of scalar names (strings)
        :param condition: A callable that accepts as many values as the length of value_names
        :param title: An optional title for this condition to be reported with the notification
        :param default_value: A default value to use when scalar values are missing (default is 1)
        :param cooldown_period: A cooldown interval (in seconds) from last notification, to prevent spamming when the
            condition is met (default is 30 seconds)
        :param only_relevant: A boolean flag to represent whether when this condition is met, only values relevant to
            this condition should be reported (default is False, i.e. report all scalars for relevant job)
        """
        if len(value_names) != len(inspect.signature(condition).parameters):
            raise RuntimeError("Number of arguments for condition {func} does not"
                               "match given number of arguments {vals}!".format(func=condition, vals=value_names))
        self.names = value_names  # type: Tuple[str, ...]
        self.condition = condition
        self.title = title or str(condition)
        self.default = default_value
        self.cooldown_period = cooldown_period or TrackerCondition.DEF_COOLDOWN_PERIOD
        self.last_time_condition_met = 0.0  # The last time condition() returned True
        self.only_relevant = only_relevant

    def __contains__(self, val_name: str):
        return val_name in self.names

    def __len__(self):
        return len(self.names)

    def __call__(self, **kwargs: float) -> bool:
        # match args/kwargs to given names
        if kwargs:
            vals = [kwargs.get(name, self.default) for name in self.names]  # type: List[float]
        else:
            vals = [self.default] * len(self.names)

        condition_result = self.condition(*vals)
        has_enough_time_passed = (time.monotonic() - self.last_time_condition_met) >= self.cooldown_period
        result = condition_result and has_enough_time_passed
        if result:
            self.last_time_condition_met = time.monotonic()
        return result


class TrackerBase:
    DEF_IMG_EXT = "png"
    """Defines common API for Tracker objects"""
    def __init__(self):
        # History of tracked information, var_name: list(vals)
        self._history_by_scalar = dict()  # type: HistoryByScalar
        # Last index which was submitted to cloud, used for statistics
        self._last_index = dict()  # type: Dict[str, int]
        self._conditions = list()  # type: List[TrackerCondition]
        self._shared_index = 0

    def add_tracked(self, val_name: str, value: float) -> Optional[TrackerCondition]:
        # Add/create to dictionaries
        if val_name in self._history_by_scalar and self._history_by_scalar[val_name][-1].idx == self._shared_index:
            self._shared_index += 1
        value_with_index = ScalarIndexPairing(value, self._shared_index)
        self._history_by_scalar.setdefault(val_name, list()).append(value_with_index)
        self._last_index.setdefault(val_name, -1)  # Initial index
        # Verify with conditions
        for condition in self._conditions:
            if val_name in condition:  # Condition is relevant for this scalar
                existing_values = [name for name in condition.names if name in self._history_by_scalar]
                kwargs = {name: self._history_by_scalar[name][-1].value for name in existing_values}
                if condition(**kwargs):
                    return condition
        return None

    def add_condition(self, *vals: str, condition: Callable[[float], bool], title: str = "", default_value=1,
                      only_relevant: bool):
        """Adds a condition for this tracker. Once a condition is met, it is reported immediately.
        If a variable listed in vals does not exist, the given default value (or 1 by default) will be sent instead. """
        self._conditions.append(TrackerCondition(*vals, condition=condition, title=title, default_value=default_value,
                                                 only_relevant=only_relevant))



    @staticmethod
    def generate_image(history: HistoryByScalar, output_path: Union[str, Path], title=None) -> Optional[str]:
        """
        Generates a plot from internal history to output_path

        If history contains no data, the image will not be generated.

        :return Absolute path to generated image if the image was generated, otherwise null
        """
        # Import matplotlib (or other future libraries) inside the function to prevent non-declaration in forked process
        import matplotlib
        matplotlib.use('svg')
        import matplotlib.pyplot as plt

        plt.clf()  # Clear figure
        for tag, vals in history.items():  # All all scalar values to plot
            if vals:  # Some values exist
                index_axis = list()
                value_axis = list()
                for value_with_index in vals:  # Separate axes
                    index_axis.append(value_with_index.idx)
                    value_axis.append(value_with_index.value)
                if len(vals) > 1:
                    plt.plot(index_axis, value_axis, label=tag, linewidth=1)
                else:  # scatter=plot the single point on x=0 :shrug:
                    plt.scatter(index_axis, value_axis, label=tag)

        if plt.gcf().axes:  # Would be empty if nothing was plotted
            plt.legend(loc='upper right')
            if title is not None:  # Title if given
                plt.title(title)
            fname, ext = os.path.splitext(output_path)  # Default extension if not provided
            if not ext:
                fname = os.path.abspath("{}.{}".format(fname, TrackerBase.DEF_IMG_EXT))
            plt.savefig(fname)
            return fname
        return None


    def _update_access(self, *names: str):
        if names:
            for name in names:
                self._last_index[name] = len(self._history_by_scalar[name]) - 1
        else:
            for val_name, vals, in self._history_by_scalar.items():
                self._last_index[val_name] = len(vals) - 1


    def _verify_scalar_names_exist(self, *names: str):
        for name in names:  # Verify all names are valid
            if name not in self._history_by_scalar:
                raise TrackedScalarNotFoundException(name=name)


    def get_updates(self, *names: str, plot: bool = True,
                    latest: bool = True) -> Tuple[HistoryByScalar, Optional[str]]:
        """Gets updates since last push update, possibly with an image

        :param names: names of value to lookup (or empty for all tracked history)
        :param plot: whether or not to plot the history and return the image path
        :param latest: whether or not to include all history, or just history since previous call
        :return tuple of data (HistoryByScalar) and location to image (if created, otherwise None)
        """
        if names:
            self._verify_scalar_names_exist(*names)
            data = dict()  # type: HistoryByScalar
            for value_name, values in self._history_by_scalar.items():
                for name in names:
                    if name == value_name:
                        data[name] = values
        else:
            data = dict(self._history_by_scalar)  # Create a copy

        imgname = None
        if plot:
            # pylint: disable=protected-access
            imgname = os.path.abspath(next(tempfile._get_candidate_names()))  # type: ignore
            imgname = self.generate_image(history=data, output_path=imgname)

        if latest:  # Trim data as needed
            for val_name, vals, in data.items():
                data[val_name] = vals[self._last_index[val_name] + 1:]

        self._update_access(*names)
        return data, imgname


    def refresh(self) -> None:
        """Cleans and updates"""
        self.clean()
        self.update()

    def get_statistics(self, val_name: str, from_beginning: bool = False):
        """Calculates viable statistics for further reporting for given value name"""
        pass

    def update(self) -> None:
        """Updates internal history stack for Tracker class"""
        pass

    def _clean(self) -> None:
        """Cleans internal history stack for Tracker class"""
        self._history_by_scalar = dict()
        self._last_index = dict()

    def clean(self) -> None:
        self._clean()


class TensorFlowTracker(TrackerBase):
    def __init__(self, path):
        global TF_EXISTS  # pylint: disable=global-statement
        if not TF_EXISTS:
            raise ModuleNotFoundError("Cannot instantiate a TensorFlowTracker without TensorFlow!")
        super().__init__()
        self.path = path
        self.ea_tracker = tfproto.EventAccumulator(path)
        self.update()

    def update(self):
        self.ea_tracker.Reload()
        for tag in self.ea_tracker.Tags()['scalars']:
            for scalar_event in self.ea_tracker.Scalars(tag):
                self.add_tracked(tag, scalar_event.value)

    def clean(self):
        self.ea_tracker._generator = tfproto._GeneratorFromPath(self.path)  # pylint: disable=protected-access
        self._clean()
