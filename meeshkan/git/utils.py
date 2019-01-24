"""Provides utilities for pulling and parsing Git commits"""
from typing import Tuple
import tempfile
import shutil
import os
from subprocess import Popen, PIPE

from ..core.config import Credentials
from ..core.service import Service

__all__ = ["run_commit", "run_branch"]

def run_commit(repo: str, commit_sha: str, entry_point: str):
    _submit_pulled_entrypoint(pull_commit(repo, commit_sha), entry_point)


def run_branch(repo, branch, entry_point):
    _submit_pulled_entrypoint(pull_branch(repo, branch), entry_point)


def pull_commit(repo, commit_sha) -> str:
    url, target_dir = _init_git(repo)
    proc = Popen(["git", "clone", url, target_dir], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    _wait_and_raise_on_error(proc)
    proc = Popen(["git", "reset", "--hard", commit_sha], stdout=PIPE, stderr=PIPE, cwd=target_dir,
                 universal_newlines=True)
    _wait_and_raise_on_error(proc)
    return target_dir

def pull_branch(repo, branch) -> str:
    url, target_dir = _init_git(repo)
    proc = Popen(["git", "clone", "--single-branch", "--branch", branch, url, target_dir], stdout=PIPE, stderr=PIPE,
                 universal_newlines=True)
    _wait_and_raise_on_error(proc)
    return target_dir


def _get_git_access_token() -> str:
    creds = Credentials.from_isi()  # Basic setup and lookup
    if creds.git_access_token is None:  # TODO should git token setup also be made available with CLI?
        raise RuntimeError("Git access token was not found! Please verify ~/.meeshkan/credentials")
    return creds.git_access_token


def _submit_pulled_entrypoint(source_dir, entry_point):  # TODO - add jobname, poll time, etc
    # TODO - add removal of source_dir after run?
    Service.api().submit((os.path.join(source_dir, entry_point), ))


def _verify_git_exists():
    if shutil.which("git") is None:
        raise RuntimeError("'git' is not installed!")


def _init_git(repo) -> Tuple[str, str]:
    _verify_git_exists()
    token = _get_git_access_token()
    return "https://{token}:x-oauth-basic@github.com/{repo}".format(token=token, repo=repo), tempfile.mkdtemp()


def _wait_and_raise_on_error(proc):
    if proc.wait() != 0:
        print(proc.returncode)
        raise RuntimeError(proc.stderr.read())
