import logging
from typing import Optional, Tuple, List
from pathlib import Path
import os
import subprocess

from nbconvert import PythonExporter

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
        if self.output_path is not None and not self.output_path.is_dir():  # Prepare output path if needed
            self.output_path.mkdir()

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

    def convert_notebook(self, notebook_file: str) -> str:
        """Converts a given notebook file to a matching Python file, to be saved in the output directory.
        :param notebook_file: Absolute path to the notebook file to-be converted.
        :return Absolute path of converted script file.
        """
        if self.output_path is None:
            raise RuntimeError("Cannot convert notebook to Python code without target directory")
        target = os.path.join(self.output_path, os.path.splitext(os.path.basename(notebook_file))[0] + ".py")
        py_code, _ = PythonExporter().from_file(notebook_file)
        with open(target, "w") as script_fd:
            script_fd.write(py_code)
            script_fd.flush()
        return target

    def to_full_path(self, args: Tuple[str, ...], cwd: str) -> List[str]:
        """Iterates over arg and prepends known files (.sh, .py) with given current working directory.
        Raises exception if any of supported file suffixes cannot be resolved to an existing file.
        :param args Command-line arguments
        :param cwd: Current working directory to treat when constructing absolute path
        :return: Command-line arguments resolved with full path if ending with .py or .sh
        """
        supported_file_suffixes = [".py", ".sh", ".ipynb"]
        new_args = list()
        for argument in args:
            new_argument = argument
            ext = os.path.splitext(argument)[1]
            if ext in supported_file_suffixes:  # A known file type
                new_argument = os.path.join(cwd, argument)
                if not os.path.isfile(new_argument):  # Verify file exists
                    raise IOError
                if ext == ".ipynb":  # Argument is notebook file -> convert to .py instead
                    new_argument = self.convert_notebook(new_argument)
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
        if self.output_path is None:  # TODO - should output_path be mandatory?
            self.popen = subprocess.Popen(self.args, stdout=subprocess.PIPE)
            return self._update_pid_and_wait()

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
