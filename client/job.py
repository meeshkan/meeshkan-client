from enum import Enum
import subprocess
from typing import Tuple
import uuid
import datetime


class JobStatus(Enum):
    CREATED = 0
    QUEUED = 1
    RUNNING = 2
    FINISHED = 3
    CANCELED = 4
    FAILED = 5


class Executable(object):
    def __init__(self):
        pass

    def launch_and_wait(self) -> int:
        """
        Base launcher
        :return: Return code (0 for success)
        """
        return 0

    def terminate(self):
        """
        Terminate execution
        :return: None
        """
        return


class ProcessExecutable(Executable):
    def __init__(self, args: Tuple[str]):
        """
        :param args: Command-line arguments to execute, fed into `Popen(args, ...)`
        """
        super().__init__()
        self.args = args
        self.popen: subprocess.Popen = None

    def launch_and_wait(self):
        """
        :return: Return code from subprocess
        """
        self.popen = subprocess.Popen(self.args, stdout=subprocess.PIPE)
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
    def __init__(self, executable: Executable, job_id: int):
        """
        :param executable: Executable instance
        :param job_id: Human-readable integer ID
        """
        self.executable = executable
        self.id = job_id  # Human-readable integer ID
        self.uuid = uuid.uuid4()  # Absolutely unique identifier
        self.created = datetime.datetime.utcnow()
        self.stale = False
        self.is_launched = False
        self.status = JobStatus.CREATED
        self.is_processed = False

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
        except IOError as e:
            print('Could not execute {}, is it executable?'.format(self.executable))
            self.status = JobStatus.FAILED
            raise e
        finally:
            self.is_processed = True

    def terminate(self):
        self.executable.terminate()

    def __str__(self):
        return "Job: %s, id %d, status %s" % (self.executable, self.id, self.status.name)

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
