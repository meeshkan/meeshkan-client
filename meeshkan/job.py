from enum import Enum
import logging
import subprocess
from typing import Tuple, Optional
import uuid
import datetime
import os
from pathlib import Path


LOGGER = logging.getLogger(__name__)


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


class ProcessExecutable(Executable):
    def __init__(self, args: Tuple[str, ...], output_path: Path = None):
        """
        Executable executed with `subprocess.Popen`.
        :param args: Command-line arguments to execute, fed into `Popen(args, ...)` _after_ prepending cwd to files
        :param output_path: Output path (directory) where to write stdout and stderr in files of same name.
               If the directory does not exist, it is created.
        """
        super().__init__()

        def to_full_path_if_known_file(arg):
            """
            Prepend .sh and .py files with current working directory.
            :param arg: Command-line argument
            :return: Command-line argument resolved with full path if ending with .py or .sh
            """
            if arg.endswith('.sh') or arg.endswith('.py'):
                return os.path.abspath(arg)
            return arg

        self.args = [to_full_path_if_known_file(arg) for arg in args]
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
                 desc: str = None):
        """
        :param executable: Executable instance
        :param job_number: Like PID, used for interacting with the job from the CLI
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
