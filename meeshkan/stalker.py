"""Module to enable remote querying of python processeses from outside the current process."""
import signal
import os
import sys
import pickle
import inspect
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

import meeshkan.notifiers
TF_EXISTS = True
try:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator, _GeneratorFromPath
except ModuleNotFoundError:
    TF_EXISTS = False  # Silently fail

DEF_IMG_EXT = ".png"


class PipedProcess(object):
    """Opens a temporary named pipe to transmit information between process A and process B"""
    PICKLE_DOWN = pickle.dumps  # Allows a way to override these for other serialization modules!
    PICKLE_UP = pickle.load
    def __init__(self, pid: int, reader: bool =False):
        """Prepares the infrastructure for one-way information "pulling"

        :param reader: Whether this class is instansiated from the reading process or the writing process
        """
        self.fname = os.path.abspath(".{}.pipe".format(pid))
        try:
            os.mkfifo(self.fname)  # Make a FIFO if possible (0 resources), otherwise we'll just have a regular file
        except OSError:
            pass
        self.f = open(self.fname, 'rb' if reader else 'wb')  # Needs to be opened continuously otherwise pipe closes
        self.is_reader = reader

    def write(self, contents) -> bool:
        """Writes `contents` to pipe. Assumes `contents` is pickleable."""
        if self.is_reader:  # The reader-end of the pipe has no access to write!
            return False
        try:
            self.f.write(self.PICKLE_DOWN(contents))
            self.f.flush()
        except (OSError, TypeError):
            return False
        return True

    def read(self):
        """Attempts to read all contents from pipe. Assume the contents in the pipe was pickled.

        :return The contents of the pipe if possible; None if this is a writing process.
        """
        if not self.is_reader:  # The writer-end of the pipe has no access to read!
            return
        return self.PICKLE_UP(self.f)

    def close(self):
        """Closes the FIFO pipe. When the writer thread closes the pipe, the pipe is removed."""
        self.f.close()
        if not self.is_reader:
            os.remove(self.fname)

def __fetch_contents(_, frame):
    """Entry point for listener when triggered by internal signal."""
    pp = PipedProcess(os.getpid())
    variables = dict()
    dictionaries = [frame.f_globals, frame.f_locals]
    # Full options for frame: https://docs.python.org/3/library/inspect.html#types-and-members
    # f_back, f_builtins, f_code, f_globals, f_lasti, f_llineno, f_locals, f_trace
    # Also see https://docs.python.org/3/reference/datamodel.html#frame-objects
    for d in dictionaries:  # Iterate over dictionaries and only keep the pickleable data
        for k, v in d.items():
            try:
                _ = pickle.dumps(v)
                variables[k] = v
            except TypeError:  # Can't pickle
                continue
    pp.write(variables)
    pp.close()  # Terminate pipe and cleanup


def peek(pid : int) -> dict:
    """Attempts to fetch contents from given PID.
    Assumes the process is a Python process with the meeshkan_listener() instansiated.

    :return A dictionary as determined by `__fetch_contents`
    """
    os.kill(pid, signal.SIGUSR1)
    pp = PipedProcess(pid, reader=True)
    variables = pp.read()
    pp.close()
    return variables


def meeshkan_listener():
    # TODO - this probably does not work on Windows, see https://docs.python.org/3/library/signal.html#signal.signal
    signal.signal(signal.SIGUSR1, __fetch_contents)


class StalkerBase(object):
    """Defines common API for Stalker objects"""
    def __init__(self):
        self._history: Dict[str, List[float]] = dict()  # Maintain a history of stalked information
        self._last_index : Dict[str, int] = -1  # Last index which was submitted to cloud, used for statistics
        self._cloud_notifier = None # meeshkan.notifiers.CloudNotifier()? Or scheduler to notify()?

    def update(self):
        """Updates internal history stack for stalker class"""
        raise NotImplementedError

    def clean(self):
        """Cleans internal history stack for stalker class"""
        raise NotImplementedError

    def generate_image(self, output_path, show=False, title: str =None):
        """Generates a plot from internal history to output_path"""
        raise NotImplementedError

    def notify_updates(self, include_image=True):
        """Notifies cloud of updates since last push update, possibly with an image"""
        raise NotImplementedError

    def refresh(self):
        """Cleans and updates"""
        self.clean()
        self.update()


class TensorFlowStalker(StalkerBase):  # TODO
    def __init__(self, path):
        global TF_EXISTS
        if not TF_EXISTS:
            raise ModuleNotFoundError("Cannot instantiate a TensorFlowStalker without TensorFlow!")
        super(TensorFlowStalker, self).__init__()
        self.path = path
        self.ea_tracker = EventAccumulator(path)
        self.update()

    def update(self):
        self.ea_tracker.Reload()
        for tag in self.ea_tracker.Tags()['scalars']:
            if tag not in self._history.keys():
                self._history[tag] = list()
            for scalar_event in self.ea_tracker.Scalars(tag):
                self._history[tag].append(scalar_event.value)

    def generate_image(self, output_path, show=False, title: str =None):
        for tag, vals in self._history.items():  # All all scalar values to plot
            plt.plot(vals, label=tag)
        plt.legend(loc='upper right')
        if title is not None:  # Title if given
            plt.title(title)
        fname, ext = os.path.splitext(output_path)  # Default extension if not provided
        if len(ext) == 0:
            ext = DEF_IMG_EXT
        plt.savefig(fname + ext)
        if show:
            plt.show()


    def clean(self):
        self.ea_tracker._generator = _GeneratorFromPath(self.path)
        self._last_index = -1
        self._history = dict()


# TODO generic stalker using peek and listen() to catch scalars by PID
# TODO TorchStalker will filter by having `backward` attrib