import logging
from typing import Tuple, Optional, List, Callable
import uuid
import os
import sys
from pathlib import Path
import tempfile
import inspect

from .base import BaseJob
from .status import JobStatus
from .executables import ProcessExecutable, Executable
from ..config import JOBS_DIR

LOGGER = logging.getLogger(__name__)

# Expose Job, SageMakerJob to upper level
__all__ = ["Job", "SageMakerJob", "IPythonJob"]  # type: List[str]


CANCELED_RETURN_CODES = [-2, -3, -9, -15]  # Signals indicating user-initiated abort
SUCCESS_RETURN_CODE = [0]  # Completeness, extend later (i.e. consider > 0 return codes as success with message?)


class IPythonJob(BaseJob):
    def __init__(self, shell, line, block=True, inline=True):
        # def __init__(self, status: JobStatus, job_uuid: Optional[uuid.UUID] = None, job_number: Optional[int] = None,
        #              name: Optional[str] = None, poll_interval: Optional[float] = None):
        super().__init__(status=JobStatus.CREATED)
        # self.shell = shell
        self.block = block
        self.inline = inline
        self.backup = dict()

        # Break arguments to function to test + arguments supplied
        args = line.split()
        func_name = args[0]
        del args[0]

        # Set up script file and location, etc
        script_path = Path(tempfile.mkdtemp())
        fname = "{fname}.py".format(fname=func_name)
        self.script_file = script_path.joinpath(fname)
        # source = inspect.getsource(self.shell.user_ns[func_name])  # Get source code for the function
        source = inspect.getsource(shell.user_ns[func_name])  # Get source code for the function
        if inline:  # Inline -> remove the definition statement and indentation
            source_lines = source.splitlines()[1:]
            spacing = len(source_lines[0]) - len(source_lines[0].lstrip())
            source_lines_unindented = [codeline[spacing:] for codeline in source_lines]
            source = "\n".join(source_lines_unindented)

        # Write the actual code
        with self.script_file.open('w') as f:
            if inline:  # Inline; set the sys.argv to include all the arguments
                f.write("import sys\n")
                f.write("sys.argv = {args}\n".format(args=[fname] + args))
            f.write(source)
            if not inline:  # Not source code -> make sure the function is called
                f.write("\n\nif __name__ == \"__main__\":\n")
                f.write("    {func}(*{args})".format(func=func_name, args=args))

        self.globs = shell.user_ns
        self.globs['__name__'] = '__main__'
        self.globs['__file__'] = self.script_file.name
        print(self.script_file)

    def terminate(self):
        pass

    def launch_and_wait(self):
        # import builtins as builtin_mod
        # IPython state restoration is taken from the IPython code according to needed flags (-i)
        #     https://github.com/ipython/ipython/blob/master/IPython/core/magics/execution.py
        # Save state:
        # save_argv = sys.argv
        # restore_main = sys.modules['__main__']
        # name_save = self.shell.user_ns['__name__']

        # Set up globals for script file
        # prog_ns = self.shell.user_ns
        # prog_ns['__name__'] = '__main__'
        # prog_ns['__file__'] = self.script_file.name
        # sys.modules['__main__'] = self.shell.user_module

        if self.block:
            # self.shell.safe_execfile(self.script_file, prog_ns, prog_ns, exit_ignore=False)
            with open(self.script_file) as f:
                exec(compile(f.read(), "some name", "exec"), self.globs)
        else:  # TODO - threading? multiprocessing?
            pass

        # Restore
        # self.shell.user_ns['__name__'] = name_save
        # self.shell.user_ns['__builtins__'] = builtin_mod
        # sys.argv = save_argv
        # sys.modules['__main__'] = restore_main

    # TODO: Add __str__, __repr__, __to_dict__


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
        super().__init__(status=JobStatus.CREATED, job_uuid=job_uuid, job_number=job_number, name=name,
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

    def add_condition(self, *val_names, condition: Callable[[float], bool], only_relevant: bool):
        self.scalar_history.add_condition(*val_names, condition=condition, only_relevant=only_relevant)

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

    @staticmethod
    def create_job(args: Tuple[str, ...], job_number: int = None, cwd: str = None, name: str = None,
                   poll_interval: int = None, description: str = None, output_path: Optional[Path] = None):
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
