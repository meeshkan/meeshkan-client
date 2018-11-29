from enum import Enum
import logging
import subprocess
from typing import Tuple, Optional, List, Union
import uuid
import datetime
import os
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
    def __init__(self):
        self.pid = None  # type: Optional[int]

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
    def to_full_path(args: Tuple[str, ...], cwd: Path):
        """Given args, iterates over arg and prepends .sh and .py files with given current working directory.
        :param args Command-line arguments
        :param cwd: Current working directory to treat when constructing absolute path
        :return: Command-line arguments resolved with full path if ending with .py or .sh
        """
        supported_file_suffixes = [".py", ".sh"]
        return [cwd.joinpath(arg) if os.path.splitext(arg)[1] in supported_file_suffixes else arg for arg in args]


class ProcessExecutable(Executable):
    def __init__(self, args: Tuple[str, ...], cwd: Optional[Union[str, Path]] = None, output_path: Path = None):
        """
        Executable executed with `subprocess.Popen`.
        :param args: Command-line arguments to execute, fed into `Popen(args, ...)` _after_ prepending cwd to files
        :param output_path: Output path (directory) where to write stdout and stderr in files of same name.
               If the directory does not exist, it is created.
        """
        super().__init__()
        cwd = Path(cwd) if cwd else Path(os.getcwd())  # Convert to Path object
        self.args = self.to_full_path(args, cwd)
        self.popen = None  # type: Optional[subprocess.Popen]
        self.output_path = output_path

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

    @staticmethod
    def from_str(args_str: str):
        return ProcessExecutable(tuple(args_str.split(' ')))

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


def _verify_python_executable(args: Tuple[str, ...]):
    """Simply checks if the first argument's extension is .py, and if so, prepends 'python' to args"""
    if len(args) > 0:    # pylint: disable=len-as-condition
        if os.path.splitext(args[0])[1] == ".py":
            args = ("python",) + args
    return args


def create_job(args: Tuple[str, ...], job_number: int, cwd: str = None, name: str = None, poll_interval: int = None,
               output_path: str = None):
    """Creates a job from given arguments"""
    job_uuid = uuid.uuid4()
    args = _verify_python_executable(args)
    LOGGER.debug("Creating job for %s", args)
    output_path = output_path if output_path and os.path.isdir(output_path) else JOBS_DIR.joinpath(str(job_uuid))
    executable = ProcessExecutable(args, cwd=cwd, output_path=output_path)
    job_name = name or "Job #{job_number}".format(job_number=job_number)
    return Job(executable, job_number=job_number, job_uuid=job_uuid, name=job_name, poll_interval=poll_interval)
