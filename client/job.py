from enum import Enum
import logging
import subprocess
from typing import Tuple
import uuid
import datetime
from pathlib import Path


LOGGER = logging.getLogger(__name__)


class JobStatus(Enum):
    CREATED = 0
    QUEUED = 1
    RUNNING = 2
    FINISHED = 3
    CANCELED = 4
    FAILED = 5

CANCELED_RETURN_CODES = [-2, -3, -9, -15] 


class Executable(object):
    def __init__(self):
        pass

    def launch_and_wait(self) -> int:  # pylint: disable=no-self-use
        """
        Base launcher
        :return: Return code (0 for success)
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
        :param args: Command-line arguments to execute, fed into `Popen(args, ...)`
        :param output_path: Output path (directory) where to write stdout and stderr in files of same name.
               If the directory does not exist, it is created.
        """
        super().__init__()
        self.args: Tuple[str, ...] = args
        self.popen: subprocess.Popen = None
        self.output_path = output_path

    def launch_and_wait(self):
        """
        :return: Return code from subprocess
        """
        if self.output_path is None:
            self.popen = subprocess.Popen(self.args, stdout=subprocess.PIPE)
            return self.popen.wait()

        if not self.output_path.is_dir():
            self.output_path.mkdir()
        stdout_file = self.output_path.joinpath('stdout')
        stderr_file = self.output_path.joinpath('stderr')
        with stdout_file.open('w') as f_stdout, stderr_file.open('w') as f_stderr:
            self.popen = subprocess.Popen(self.args, stdout=f_stdout, stderr=f_stderr)
            return self.popen.wait()

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
        self.id = job_uuid or uuid.uuid4()  # Absolutely unique identifier
        self.number = job_number  # Human-readable integer ID
        self.created = datetime.datetime.utcnow()
        self.stale = False
        self.is_launched = False
        self.status = JobStatus.CREATED
        self.is_processed = False
        self.name = name or f"Job #{self.number}"
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
            # TODO Get rid of magic return code constants
            self.status = JobStatus.FINISHED if return_code == 0 else \
                JobStatus.CANCELED if return_code == -15 else JobStatus.FAILED
            return return_code
        except IOError as ex:
            LOGGER.error(f"Could not execute, is the job executable? Job: {str(self.executable)}")
            self.status = JobStatus.FAILED
            raise ex
        finally:
            self.is_processed = True

    def terminate(self):
        self.executable.terminate()

    def __str__(self):
        return f"Job: {self.executable}, #{self.number} ({self.id}) - {self.status.name}"

    def mark_stale(self):
        """
        Mark job as stale (canceled)
        :return:
        """
        self.stale = True

    def cancel(self):
        """
        Cancel job and update status
        :return:
        """
        self.mark_stale()
        self.terminate()
        if not self.is_launched:
            self.status = JobStatus.CANCELED  # Safe to modify as worker has not started

    def to_dict(self):
        return {
            'id': str(self.id),
            'number': self.number,
            'status': self.status.name,
            'args': str(self.executable)
        }
