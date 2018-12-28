import os
from pathlib import Path
import uuid

import pytest


from meeshkan.core.job import ProcessExecutable, Job

JOBS_OUTPUT_PATH = Path(os.path.dirname(__file__)).joinpath('resources', 'jobs')

STDOUT_FILE = JOBS_OUTPUT_PATH.joinpath('stdout')
STDERR_FILE = JOBS_OUTPUT_PATH.joinpath('stderr')


@pytest.fixture
def clean_up():
    def remove_file(path: Path):
        if path.is_file():
            os.remove(str(path))

    def remove_stdout_stderr():
        remove_file(STDOUT_FILE)
        remove_file(STDERR_FILE)

    yield remove_stdout_stderr()
    remove_stdout_stderr()


def test_proc_exec_output_path(clean_up):  # pylint: disable=unused-argument,redefined-outer-name
    some_string = str(uuid.uuid4())
    executable = ProcessExecutable(args=('echo', some_string), output_path=JOBS_OUTPUT_PATH)
    executable.launch_and_wait()
    assert STDOUT_FILE.is_file(), "stdout file should be created after the process was launched"
    assert STDERR_FILE.is_file(), "stderr file should be created after the process was launched"
    with open(STDOUT_FILE, 'r') as file:
        text = file.read()
    assert text == some_string + '\n', "Job was expected to write '{}' to stdout!".format(some_string)


def test_proc_exec_args_raise_file_not_found():
    with pytest.raises(IOError):
        ProcessExecutable(args=('python', "non_existing.py"))


def test_job_args_to_full_path_with_runtime():
    cwd, base = os.path.split(__file__)
    job = Job.create_job(args=(base, 'another_argument'), cwd=cwd, job_number=1)
    assert len(job.executable.args) == 3, "`create_job` should add the python executable to the argument list"
    assert job.executable.args[1] == __file__, "Expected '{}' to be full " \
                                               "path '{}'".format(job.executable.args[1], __file__)