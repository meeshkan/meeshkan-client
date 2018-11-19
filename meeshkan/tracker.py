"""Module to enable remote querying of python processeses from outside the current process."""
import os
from numbers import Number
from typing import Union, List, Dict, Tuple, Optional
from pathlib import Path
import tempfile
import logging

import matplotlib
try:
    import matplotlib.pyplot as plt
except ImportError:
    # Try setting explicit backend for MacOS, see
    # https://stackoverflow.com/questions/21784641/installation-issue-with-matplotlib-python
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt

import meeshkan.__types__  # To prevent cyclic import
import meeshkan.exceptions


TF_EXISTS = True
try:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator, _GeneratorFromPath
except ModuleNotFoundError:
    TF_EXISTS = False  # Silently fail

LOGGER = logging.getLogger(__name__)


class TrackerBase(object):
    DEF_IMG_EXT = ".png"
    """Defines common API for Tracker objects"""
    def __init__(self):
        # History of tracked information, var_name: list(vals)
        self._history_by_scalar = dict()  # type: meeshkan.__types__.HistoryByScalar
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
    def generate_image(history: Dict[str, List[Number]], output_path: Union[str, Path], show: bool = False,
                       title: str = None) -> None:
        """Generates a plot from internal history to output_path"""
        for tag, vals in history.items():  # All all scalar values to plot
            plt.plot(vals, label=tag)
        plt.legend(loc='upper right')
        if title is not None:  # Title if given
            plt.title(title)
        fname, ext = os.path.splitext(output_path)  # Default extension if not provided
        if not ext:
            ext = TrackerBase.DEF_IMG_EXT
        plt.savefig(fname + ext)
        if show:
            plt.show()

    def _update_access(self, name: str = ""):
        if name:
            if name in self._history_by_scalar:
                self._last_index[name] = len(self._history_by_scalar[name]) - 1
        else:
            for val_name, vals, in self._history_by_scalar.items():
                self._last_index[val_name] = len(vals) - 1

    def get_updates(self, name: str = "", plot: bool = True,
                    latest: bool = True) -> Tuple[meeshkan.HistoryByScalar, Optional[str]]:
        """Gets updates since last push update, possibly with an image

        :param name: name of value to lookup (or empty for all tracked history)
        :param plot: whether or not to plot the history and return the image path
        :param latest: whether or not to include all history, or just history since previous call
        :return tuple of data (meeshkan.History) and location to image (if created, otherwise None)
        """
        if name and name not in self._history_by_scalar:
            raise meeshkan.exceptions.TrackedScalarNotFoundException(name=name)
        if name:
            data = dict()  # type: meeshkan.__types__.HistoryByScalar
            for scalar_name, value_list in self._history_by_scalar.items():
                if scalar_name == name:
                    data[scalar_name] = value_list
        else:
            data = dict(self._history_by_scalar)  # Create a copy
        if latest:  # Trim data as needed
            for val_name, vals, in data.items():
                data[val_name] = vals[self._last_index[val_name] + 1:]
        self._update_access(name)
        if plot:
            # pylint: disable=protected-access
            imgname = next(tempfile._get_candidate_names())  # type: ignore
            imgname = os.path.abspath("{}.png".format(imgname))
            self.generate_image(history=data, output_path=imgname)
            return data, imgname
        return data, None


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
        self.ea_tracker = EventAccumulator(path)
        self.update()

    def update(self):
        self.ea_tracker.Reload()
        for tag in self.ea_tracker.Tags()['scalars']:
            for scalar_event in self.ea_tracker.Scalars(tag):
                self.add_tracked(tag, scalar_event.value)

    def clean(self):
        self.ea_tracker._generator = _GeneratorFromPath(self.path)  # pylint: disable=protected-access
        self._clean()
