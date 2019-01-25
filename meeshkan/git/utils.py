"""Provides utilities for pulling and parsing Git commits"""
from typing import Tuple, Optional
import tempfile
import shutil
import os
from subprocess import Popen, PIPE

from ..core import config
from ..core.service import Service

__all__ = ["submit"]

def submit(repo: str, entry_point: str, branch: str = None, commit_sha: str = None,
           job_name: Optional[str] = None, poll_interval: Optional[float] = None):
    """Submits a git repository as a job to the agent.
    :param repo: A string describing a **GitHub** repository in plain <user or organization>/<repo name> format
    :param entry_point: A path (relevant to the repository) for the entry point (or file to run)
    :param branch: Optional string, describing the branch on which to work (checkout the branch when cloning locally)
    :param commit_sha: Optional string, a commit reference to reset to
    :param job_name: Optional name to give to the job
    :param poll_interval: Optional float, how often to poll for changes from job
    """
    api = Service.api()  # Raise if agent is not running
    source_dir = pull_repo(repo, branch=branch, commit_sha=commit_sha)
    api.submit((os.path.join(source_dir, entry_point),), name=job_name, poll_interval=poll_interval)


def pull_repo(repo: str, branch: str = None, commit_sha: str = None) -> str:
    """Pulls a git repository to a temporary folder.

    :param repo: The GitHub repository to pull, in a plain <user/organization>/<repo name> format
        # TODO: When we add more support, this should be parsed to include also full URLs etc
    :param branch: An optional branch to download; pulls the repo and checkouts the given branch
    :param commit_sha: An optional commit to revert to; pulls the repo/branch and hard resets to given commit
    :return The temporary folder with relevant pulled content
    """
    url, target_dir = _init_git(repo)
    args = ["git", "clone"]
    if branch is not None:  # Checkout the relevant branch
        args += ["--single-branch", "--branch", branch]
    args += [url, target_dir]

    proc = Popen(args, stdout=PIPE, stderr=PIPE, universal_newlines=True)  # TODO: Use async in case it's a large pull?
    _wait_and_raise_on_error(proc)
    if commit_sha is not None:  # Revert to relevant commit SHA
        proc = Popen(["git", "reset", "--hard", commit_sha], stdout=PIPE, stderr=PIPE, cwd=target_dir,
                     universal_newlines=True)
        _wait_and_raise_on_error(proc)
    return target_dir


def _get_git_access_token() -> str:
    if config.CREDENTIALS is None:
        config.init_config()
    token = config.CREDENTIALS.git_access_token  # type: ignore
    if token is None:
        raise RuntimeError("Git access token was not found! Please verify ~/.meeshkan/credentials")
    return token


def _verify_git_exists():
    if shutil.which("git") is None:
        raise RuntimeError("'git' is not installed!")


def _init_git(repo) -> Tuple[str, str]:
    """First steps in accessing a github repository:
    - Verifies local `git` is indeed installed
    - Creates a temporary folder to store the git contents
    - Constructs the OAuth based url to the given repository

    :return A tuple consisting of the access URL and the temporary folder path
    """
    _verify_git_exists()
    token = _get_git_access_token()
    return "https://{token}:x-oauth-basic@github.com/{repo}".format(token=token, repo=repo), tempfile.mkdtemp()


def _wait_and_raise_on_error(proc):
    if proc.wait() != 0:
        raise RuntimeError(proc.stderr.read())
