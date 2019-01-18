import logging
from typing import Optional, Tuple
from pathlib import Path
import os
import subprocess

LOGGER = logging.getLogger(__name__)

# Expose only valid classes
__all__ = ["ProcessExecutable"]

class Executable:
    """
    Base class for all executables executable by the Meeshkan agent, either as subprocesses, functions, or other means
    """
    STDOUT_FILE = 'stdout'
    STDERR_FILE = 'stderr'

    def __init__(self, output_path: Path = None):
        super().__init__()
        self.pid = None  # type: Optional[int]
        self.output_path = output_path  # type: Optional[Path]

    def launch_and_wait(self) -> int:  # pylint: disable=no-self-use
        """
        Base launcher
        :return:  Return code (0 for success)
        """
        return 0

    @property
    def stdout(self):
        return self.output_path.joinpath(self.STDOUT_FILE) if self.output_path else None

    @property
    def stderr(self):
        return self.output_path.joinpath(self.STDERR_FILE) if self.output_path else None

    def terminate(self):
        raise NotImplementedError

    @staticmethod
    def to_full_path(args: Tuple[str, ...], cwd: str):
        """Iterates over arg and prepends known files (.sh, .py) with given current working directory.
        Raises exception if any of supported file suffixes cannot be resolved to an existing file.
        :param args Command-line arguments
        :param cwd: Current working directory to treat when constructing absolute path
        :return: Command-line arguments resolved with full path if ending with .py or .sh
        """
        supported_file_suffixes = [".py", ".sh"]
        new_args = list()
        for argument in args:
            new_argument = argument
            if os.path.splitext(argument)[1] in supported_file_suffixes:  # A known file type
                new_argument = os.path.join(cwd, argument)
                if not os.path.isfile(new_argument):  # Verify file exists
                    raise IOError
            new_args.append(new_argument)
        return new_args


class ProcessExecutable(Executable):
    def __init__(self, args: Tuple[str, ...], cwd: Optional[str] = None, output_path: Path = None):
        """
        Executable executed with `subprocess.Popen`.
        :param args: Command-line arguments to execute, fed into `Popen(args, ...)` _after_ prepending cwd to files
        :param output_path: Output path (directory) where to write stdout and stderr in files of same name.
               If the directory does not exist, it is created.
        """
        super().__init__(output_path)
        cwd = cwd or os.getcwd()
        self.args = self.to_full_path(args, cwd)
        self.popen = None  # type: Optional[subprocess.Popen]

    def _update_pid_and_wait(self):
        """Updates the pid for the time the executable is running and returns the return code from the executable"""
        if self.popen is not None:
            self.pid = self.popen.pid
            res = self.popen.wait()
            self.pid = None
            return res
        raise RuntimeError("Process not instantiated for this job! ({args})".format(args=self.args))

    def launch_and_wait(self):
        """
        :return: Return code from subprocess
        """
        if self.output_path is None:
            self.popen = subprocess.Popen(self.args, stdout=subprocess.PIPE)
            return self._update_pid_and_wait()

        if not self.output_path.is_dir():
            self.output_path.mkdir()
        with self.stdout.open(mode='w') as f_stdout, self.stderr.open(mode='w') as f_stderr:
            self.popen = subprocess.Popen(self.args, stdout=f_stdout, stderr=f_stderr)
            return self._update_pid_and_wait()

    def terminate(self):
        if self.popen is not None:
            self.popen.terminate()

    def __str__(self):
        return ' '.join(self.args)

    def __repr__(self):
        """Formats arguments by truncating filenames and paths if available to '...'.
        Example: /usr/bin/python3 /some/path/to/a/file/to/run.py -> ...python3 ...run.py"""
        truncated_args = list()
        for arg in self.args:
            if os.path.exists(arg):
                truncated_args.append("...{arg}".format(arg=os.path.basename(arg)))
            else:
                truncated_args.append(arg)
        return ' '.join(truncated_args)
