import logging
from typing import Tuple, Optional, List, Callable
import uuid
import os
import sys
from pathlib import Path

from .base import BaseJob
from .status import JobStatus
from .executables import ProcessExecutable, Executable
from ..config import JOBS_DIR

LOGGER = logging.getLogger(__name__)

# Expose Job, SageMakerJob to upper level
__all__ = ["Job", "SageMakerJob", "ExternalJob"]  # type: List[str]


CANCELED_RETURN_CODES = [-2, -3, -9, -15]  # Signals indicating user-initiated abort
SUCCESS_RETURN_CODE = [0]  # Completeness, extend later (i.e. consider > 0 return codes as success with message?)


class SageMakerJob(BaseJob):
    """
    Job run by SageMaker, meeshkan doing only monitoring.
    """
    def __init__(self,
                 job_name: str,
                 status: JobStatus,
                 poll_interval: Optional[float]):
        super().__init__(status=status,
                         job_uuid=None,
                         job_number=0,  # TODO
                         name=job_name,
                         poll_interval=poll_interval)

    def terminate(self):
        raise NotImplementedError


class ExternalJob(BaseJob):
    def __init__(self, pid: int, job_uuid: uuid.UUID = None, name: str = None,
                 desc: str = None, poll_interval: Optional[float] = None):
        """
        :param pid: External job process ID
        :param job_uuid
        :param name
        :param desc
        :param poll_interval
        """
        super().__init__(status=JobStatus.CREATED,
                         job_uuid=job_uuid,
                         job_number=0,
                         name=name,
                         poll_interval=poll_interval)
        self.pid = pid
        self.description = desc

    @staticmethod
    def create(pid: int, name: str, poll_interval=BaseJob.DEF_POLLING_INTERVAL) -> 'ExternalJob':
        return ExternalJob(pid=pid, name=name, poll_interval=poll_interval)

    def terminate(self):
        raise NotImplementedError


class Job(BaseJob):  # TODO Change base properties to use composition instead of inheritance?
    """
    Job submitted to the Meeshkan scheduler for running (rename as `SchedulerJob`)?
    """

    def __init__(self, executable: Executable, job_number: int, job_uuid: uuid.UUID = None, name: str = None,
                 desc: str = None, poll_interval: Optional[float] = None):
        """
        :param executable: Executable instance
        :param job_number: Like PID, used for interacting with the job from the CLI
        :param job_uuid
        :param name
        :param desc
        :param poll_interval
        """
        super().__init__(status=JobStatus.CREATED,
                         job_uuid=job_uuid,
                         job_number=job_number,
                         name=name,
                         poll_interval=poll_interval)
        self.executable = executable
        self.description = desc or str(executable)

    # Properties

    @property
    def pid(self):
        return self.executable.pid

    @property
    def output_path(self):
        return self.executable.output_path

    @property
    def stdout(self):
        return self.executable.stdout

    @property
    def stderr(self):
        return self.executable.stderr

    def launch_and_wait(self) -> int:
        """
        Run the executable, updating job status accordingly
        :return: return code
        """
        try:
            self.status = JobStatus.RUNNING
            return_code = self.executable.launch_and_wait()
            if return_code in SUCCESS_RETURN_CODE:
                self.status = JobStatus.FINISHED
            elif return_code in CANCELED_RETURN_CODES:
                self.status = JobStatus.CANCELED
            else:
                self.status = JobStatus.FAILED
            return return_code
        except Exception as ex:
            LOGGER.exception("Failed executing job")
            self.status = JobStatus.FAILED
            raise ex

    def terminate(self):
        self.executable.terminate()

    def __str__(self):
        return "Job: {executable}, #{number}, ({id}) - {status}".format(executable=self.executable, number=self.number,
                                                                        id=self.id, status=self.status.name)

    def cancel(self):
        """
        Cancel job and update status
        :return:
        """
        self.terminate()
        if not self.status.is_launched:
            self.status = JobStatus.CANCELLED_BY_USER  # Safe to modify as worker has not started

    def to_dict(self):
        return {'number': self.number,
                'id': str(self.id),
                'name': self.name,
                'status': self.status.name,
                'args': repr(self.executable)}

    # TODO - change to a factory method outside `Job` class?
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
        """Checks if the first argument's extension is one of .py, .ipy or .ipynb, and prepends the matching
        interpreter to args."""
        if args is None:
            return None
        ext = os.path.splitext(args[0])[1]
        if ext == ".py":
            #TODO: default executable should be in config.yaml?
            args = (sys.executable or "python",) + args  # Full path to interpreter or "python" alias by default
        if ext in [".ipy", ".ipynb"]:
            # Check if `ipython` is installed
            import importlib
            ipython_exists = importlib.util.find_spec("IPython") is not None
            if ipython_exists:
                args = ("ipython",) + args
            else:  # Default being python; if IPython doesn't exist, magic commands will be eliminated
                args = (sys.executable or "python",) + args
        return args
