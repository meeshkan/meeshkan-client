"""Module to enable remote querying of python processeses from outside the current process."""
import signal
import os
import sys
import pickle
import inspect

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

def meeshkan_track(func):  # TODO - future decorator to run a method and return intermediate values? Or just track progress of variables?
    def internal_contents(*args, *kwargs):
        pass
    return internal_contents()