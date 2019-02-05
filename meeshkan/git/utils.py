"""Provides utilities for pulling and parsing Git commits"""
from typing import Optional, Union
import tempfile
import shutil
import os
from subprocess import Popen, PIPE
from pathlib import Path

from ..core import config
from ..core.service import Service

__all__ = ["submit_git"]


def submit_git(repo: str, entry_point: str, branch: str = None, commit_sha: str = None,
               job_name: Optional[str] = None, report_interval_secs: Optional[float] = None):
    """Submits a GitHub repository as a job to the agent. The agent must be running.

    Example::

        # A basic call would pull the repository at its current state (default branch) and
        # run the entry point file.
        meeshkan.git.submit(repo="Meeshkan/meeshkan-client",
                            entry_point="examples/pytorch_mnist.py",
                            job_name="example #1", report_interval_secs=60)

        # A call with branch name would run the given branch from its most updated commit.
        meeshkan.git.submit(repo="Meeshkan/meeshkan-client",
                            entry_point="examples/pytorch_mnist.py",
                            branch="dev",
                            job_name="example #2",
                            report_interval_secs=10)

        # A call with a given commit will locally reset the repository to the state for
        # that commit. Commit_sha can be either short SHA or the full one.
        # In this case, either "61657d7" or "1657d79bfd92fda7c19d6ec273b09068f96a777"
        # would be fine.
        meeshkan.git.submit(repo="Meeshkan/meeshkan-client",
                            entry_point="examples/pytorch_mnist.py",
                            commit_sha="61657d7",
                            job_name="example #3",
                            report_interval_secs=30)

        # Branch and commit_sha may be used together, but commit SHA has precedence,
        # so the following is identical to example #3:
        meeshkan.git.submit(repo="Meeshkan/meeshkan-client",
                            entry_point="examples/pytorch_mnist.py",
                            branch="release-0.1.0",
                            commit_sha="61657d7",
                            job_name="identical to example #3")

    :param repo: A string describing a **GitHub** repository in plain <user or organization>/<repo name> format
    :param entry_point: A path (relevant to the repository) for the entry point (or file to run)
    :param branch: Optional string, describing the branch on which to work (checkout the branch when cloning locally)
    :param commit_sha: Optional string, a commit reference to reset to
    :param job_name: Optional name to give to the job
    :param report_interval_secs: Optional float, notification report interval in seconds.
    :returns: :py:class:`Job` object
    """
    api = Service.api()  # Raise if agent is not running
    gitrunner = GitRunner(repo)
    source_dir = gitrunner.pull_repo(branch=branch, commit_sha=commit_sha)
    return api.submit((os.path.join(source_dir, entry_point),), name=job_name, poll_interval=report_interval_secs)


class GitRunner:
    def __init__(self, repo):
        """Initializes a GitRunner by running the first steps in accessing a github repository:
            - Verifies local `git` is indeed installed
            - Creates a temporary folder to store the git contents
        :param repo: The GitHub repository to pull, in a plain <user/organization>/<repo name> format
            # TODO: When we add more support, this should be parsed to include also full URLs etc
        :return A tuple consisting of the access URL and the temporary folder path
        """
        GitRunner._verify_git_exists()
        self.repo = repo
        self.target_dir = tempfile.mkdtemp()

    def pull_repo(self, branch: str = None, commit_sha: str = None) -> str:
        """Pulls a git repository to a temporary folder.

        :param branch: An optional branch to download; pulls the repo and checkouts the given branch
        :param commit_sha: An optional commit to revert to; pulls the repo/branch and hard resets to given commit
        :return The temporary folder with relevant pulled content
        """
        args = ["git", "clone"]
        if branch is not None and commit_sha is None:  # Checkout the relevant branch (if commit not given)
            args += ["--depth", "1", "--branch", branch]
        args += [self.url, self.target_dir]

        # TODO: Use async Popen in case it's a large pull?
        proc = Popen(args, stdout=PIPE, stderr=PIPE, universal_newlines=True)
        GitRunner._wait_and_raise_on_error(proc)
        if commit_sha is not None:  # Revert to relevant commit SHA
            proc = Popen(["git", "reset", "--hard", commit_sha], stdout=PIPE, stderr=PIPE, cwd=self.target_dir,
                         universal_newlines=True)
            GitRunner._wait_and_raise_on_error(proc)
        return self.target_dir

    @property
    def url(self):
        return "https://{token}:x-oauth-basic@github.com/{repo}".format(token=GitRunner._git_access_token(),
                                                                        repo=self.repo)

    @staticmethod
    def _git_access_token(credentials: Optional[Union[Path, str]] = None) -> str:
        if config.CREDENTIALS is None:
            config.init_config()
        if credentials is not None:
            token = config.Credentials.from_isi(Path(credentials)).git_access_token
        else:  # Defaults automatically to the global CREDENTIALS
            token = config.CREDENTIALS.git_access_token  # type: ignore
        if token is None:
            raise GitRunner.GitException("Git access token was not found! Try running 'meeshkan setup'.")
        return token

    @staticmethod
    def _verify_git_exists():
        if shutil.which("git") is None:
            raise GitRunner.GitException("'git' is not installed!")

    @staticmethod
    def _wait_and_raise_on_error(proc):
        if proc.wait() != 0:
            raise RuntimeError(proc.stderr.read())

    class GitException(Exception):
        pass
