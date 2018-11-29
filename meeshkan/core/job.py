from enum import Enum
import logging
import subprocess
from typing import Tuple, Optional, List, Union
import uuid
import datetime
import os
import sys
from pathlib import Path

from .config import JOBS_DIR


LOGGER = logging.getLogger(__name__)


# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


class JobStatus(Enum):
    CREATED = 0  # New job
    QUEUED = 1  # Added to QueueProcessor
    RUNNING = 2  # Currently running
    FINISHED = 3  # Finished task successfully
    CANCELED = 4  # Aborted outside of scheduler (e.g. user used `kill -9 ...`)
    FAILED = 5  # Failed due to some errors
    CANCELLED_BY_USER = 10  # Marked cancelled by service


CANCELED_RETURN_CODES = [-2, -3, -9, -15]  # Signals indicating user-initiated abort
SUCCESS_RETURN_CODE = [0]  # Completeness, extend later (i.e. consider > 0 return codes as success with message?)


class Executable(object):
    def __init__(self, output_path: Path = None):
        self.pid = None  # type: Optional[int]
        self.output_path = output_path  # type: Optional[Path]

    def launch_and_wait(self) -> int:  # pylint: disable=no-self-use
        """
        Base launcher
        :return:  Return code (0 for success)
        """
        return 0

    def terminate(self):  # pylint: disable=no-self-use
        """
        Terminate execution
        :return: None
        """
        return

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
        stdout_file = self.output_path.joinpath('stdout')
        stderr_file = self.output_path.joinpath('stderr')
        with stdout_file.open(mode='w') as f_stdout, stderr_file.open(mode='w') as f_stderr:
            self.popen = subprocess.Popen(self.args, stdout=f_stdout, stderr=f_stderr)
            return self._update_pid_and_wait()

    def terminate(self):
        if self.popen is not None:
            self.popen.terminate()

    def __str__(self):
        return ' '.join(self.args)


class Job(object):
    def __init__(self, executable: Executable, job_number: int, job_uuid: uuid.UUID = None, name: str = None,
                 desc: str = None, poll_interval: float = None):
        """
        :param executable: Executable instance
        :param job_number: Like PID, used for interacting with the job from the CLI
        :param job_uuid
        :param name
        :param desc
        :param poll_interval
        """
        self.executable = executable
        # Absolutely unique identifier
        self.id = job_uuid or uuid.uuid4()  # pylint: disable=invalid-name
        self.number = job_number  # Human-readable integer ID
        self.created = datetime.datetime.utcnow()
        self.is_launched = False
        self.status = JobStatus.CREATED
        self.is_processed = False
        self.name = name or "Job #{number}".format(number=self.number)
        self.description = desc or str(executable)
        self.poll_time = poll_interval

    def launch_and_wait(self) -> int:
        """
        Run the executable, updating job status accordingly
        :return: return code
        """
        try:
            self.status = JobStatus.RUNNING
            self.is_launched = True
            return_code = self.executable.launch_and_wait()
            if return_code in SUCCESS_RETURN_CODE:
                self.status = JobStatus.FINISHED
            elif return_code in CANCELED_RETURN_CODES:
                self.status = JobStatus.CANCELED
            else:
                self.status = JobStatus.FAILED
            return return_code
        except IOError as ex:
            LOGGER.exception("Could not execute, is the job executable? Job: %s", str(self.executable))
            self.status = JobStatus.FAILED
            raise ex
        finally:
            self.is_processed = True

    def terminate(self):
        self.executable.terminate()

    def __str__(self):
        return "Job: {executable}, #{number}, ({id}) - {status}".format(executable=self.executable, number=self.number,
                                                                        id=self.id, status=self.status.name)

    @property
    def stale(self):
        return self.status == JobStatus.CANCELLED_BY_USER

    @property
    def pid(self):
        return self.executable.pid

    @property
    def output_path(self):
        return self.executable.output_path

    def cancel(self):
        """
        Cancel job and update status
        :return:
        """
        self.terminate()
        if not self.is_launched:
            self.status = JobStatus.CANCELLED_BY_USER  # Safe to modify as worker has not started

    def to_dict(self):
        return {'id': str(self.id),
                'number': self.number,
                'name': self.name,
                'status': self.status.name,
                'args': str(self.executable)}

    @staticmethod
    def create_job(args: Tuple[str, ...], job_number: int, cwd: str = None, name: str = None, poll_interval: int = None,
                   description: str = None, output_path: Optional[Path] = None):
        """Creates a job from given arguments.
        :param args: arguments that make up an executable
        :param job_number: human-readable job number
        :param cwd: current working directory, if None, defaults to the directory where the daemon was started in
        :param name: human readable job name
        :param poll_interval: interval (in seconds) for polling registered scalar values from the given job
        :param description: A free text description for the job
        :param output_path: path to save stdout, stderr and graphs created for the job, or None for default location.
        :return A new Job created from the given arguments
        :raises IOError if any of the files in args cannot be found
        """
        job_uuid = uuid.uuid4()
        args = Job.__verify_python_executable(args)
        LOGGER.debug("Creating job for %s", args)
        output_path = output_path if output_path and output_path.is_dir() else JOBS_DIR.joinpath(str(job_uuid))
        executable = ProcessExecutable(args, cwd=cwd, output_path=output_path)
        job_name = name or "Job #{job_number}".format(job_number=job_number)
        return Job(executable, job_number=job_number, job_uuid=job_uuid, name=job_name, poll_interval=poll_interval,
                   desc=description)


    @staticmethod
    def __verify_python_executable(args: Tuple[str, ...]):
        """Checks if the first argument's extension is .py, and prepends the full path to Python interpreter to args.
        If the full path is unavailable, defaults to using 'python' alias as runtime. """
        if len(args) > 0:    # pylint: disable=len-as-condition
            if os.path.splitext(args[0])[1] == ".py":
                #TODO: default executable should be in config.yaml?
                args = (sys.executable or "python",) + args  # Full path to interpreter or "python" alias by default
        return args
