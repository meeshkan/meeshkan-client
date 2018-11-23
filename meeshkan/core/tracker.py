"""Module to enable remote querying of python processeses from outside the current process."""
import os
from numbers import Number
from typing import Union, List, Dict, Tuple, Optional, Callable, Any
from pathlib import Path
import uuid
import tempfile
import logging
import sys
import asyncio

from .job import Job
from ..__types__ import HistoryByScalar
from ..exceptions import TrackedScalarNotFoundException

TF_EXISTS = True
try:
    import tensorboard.backend.event_processing.event_accumulator as tfproto
except ModuleNotFoundError:
    TF_EXISTS = False  # Silently fail

LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class TrackingPoller(object):
    DEF_POLLING_INTERVAL = 3600  # Default is notifications every hour.
    def __init__(self, notify_function: Callable[[uuid.UUID], Any]):
        self._notify = notify_function

    async def poll(self, job: Job):
        """Asynchronous polling function for scalars in given job"""
        LOGGER.debug("Starting job tracking for job %s", job)
        sleep_time = job.poll_time or TrackingPoller.DEF_POLLING_INTERVAL
        try:
            while True:
                await asyncio.sleep(sleep_time)  # Let other tasks run meanwhile
                self._notify(job.id)  # Synchronously notify of changes.
        except asyncio.CancelledError:
            LOGGER.debug("Job tracking cancelled for job %s", job.id)


class TrackerBase(object):
    DEF_IMG_EXT = "png"
    """Defines common API for Tracker objects"""
    def __init__(self):
        # History of tracked information, var_name: list(vals)
        self._history_by_scalar = dict()  # type: HistoryByScalar
        # Last index which was submitted to cloud, used for statistics
        self._last_index = dict()  # type: Dict[str, int]

    def add_tracked(self, val_name: str, value: Union[Number, List[Number]]) -> None:
        if isinstance(value, Number):
            value = [value]
        if val_name not in self._history_by_scalar:
            self._history_by_scalar[val_name] = value
            self._last_index[val_name] = -1  # Marks initial index
        else:
            self._history_by_scalar[val_name] += value

    @staticmethod
    def generate_image(history: HistoryByScalar, output_path: Union[str, Path], title=None) -> Optional[str]:
        """
        Generates a plot from internal history to output_path

        If history contains no data, the image will not be generated.

        :return Absolute path to generated image if the image was generated, otherwise null
        """
        # Import matplotlib (or other future libraries) inside the function to prevent non-declaration in forked process
        import matplotlib  # TODO - switch to a different backend (macosx?) or different module for plots (ggplot?)
        if sys.platform == 'darwin':  # MacOS fix - try setting explicit backend, see
            #  https://stackoverflow.com/questions/21784641/installation-issue-with-matplotlib-python
            matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt

        has_plotted = False
        plt.clf()  # Clear figure
        for tag, vals in history.items():  # All all scalar values to plot
            if len(vals) > 1:  # Only bother plotting values with at least 2 data points (a line in space!)
                has_plotted = True
                plt.plot(vals, label=tag)
        if has_plotted:
            plt.legend(loc='upper right')
            if title is not None:  # Title if given
                plt.title(title)
            fname, ext = os.path.splitext(output_path)  # Default extension if not provided
            if not ext:
                fname = os.path.abspath("{}.{}".format(fname, TrackerBase.DEF_IMG_EXT))
            plt.savefig(fname)
            return fname
        return None

    def _update_access(self, name: str = ""):
        if name:
            if name in self._history_by_scalar:
                self._last_index[name] = len(self._history_by_scalar[name]) - 1
        else:
            for val_name, vals, in self._history_by_scalar.items():
                self._last_index[val_name] = len(vals) - 1

    def get_updates(self, name: str = "", plot: bool = True,
                    latest: bool = True) -> Tuple[HistoryByScalar, Optional[str]]:
        """Gets updates since last push update, possibly with an image

        :param name: name of value to lookup (or empty for all tracked history)
        :param plot: whether or not to plot the history and return the image path
        :param latest: whether or not to include all history, or just history since previous call
        :return tuple of data (HistoryByScalar) and location to image (if created, otherwise None)
        """
        if name and name not in self._history_by_scalar:
            raise TrackedScalarNotFoundException(name=name)

        if name:
            data = dict()  # type: HistoryByScalar
            for scalar_name, value_list in self._history_by_scalar.items():
                if scalar_name == name:
                    data[scalar_name] = value_list
        else:
            data = dict(self._history_by_scalar)  # Create a copy

        imgname = None
        if plot:  # TODO: maybe include an output directory so we write these directly to the job folder?
            # pylint: disable=protected-access
            imgname = os.path.abspath(next(tempfile._get_candidate_names()))  # type: ignore
            imgname = self.generate_image(history=data, output_path=imgname)

        if latest:  # Trim data as needed
            for val_name, vals, in data.items():
                data[val_name] = vals[self._last_index[val_name] + 1:]
        self._update_access(name)
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
        super(TensorFlowTracker, self).__init__()
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
