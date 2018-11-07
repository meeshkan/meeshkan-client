import os
from pathlib import Path
import uuid

import pytest


from client.job import ProcessExecutable

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
    assert STDOUT_FILE.is_file()
    assert STDERR_FILE.is_file()
    with open(STDOUT_FILE, 'r') as file:
        text = file.read()
    assert text == some_string + '\n'
