"""Provides utilities for pulling and parsing Git commits"""
from typing import List
import base64

from github import Github

from ..core.config import Credentials

__all__ = ["pull_commit"]  # type: List[str]

def pull_commit(repo: str, commit_sha: str, download_all=False):
    """"""
    creds = Credentials.from_isi()  # Basic setup and lookup
    if creds.git_access_token is None:  # TODO should git token setup also be made available with CLI?
        raise RuntimeError("Git access token was not found! Please verify ~/.meeshkan/credentials")
    git = Github(creds.git_access_token)
    repo = git.get_repo(repo)
    commit = repo.get_commit(commit_sha)
    # Get differences between the default branch and that commit.
    def_branch_last_commit = repo.get_branch(repo.default_branch).commit
    changed_files = repo.compare(def_branch_last_commit.sha, commit.sha).files
    for file in changed_files:
        content_file = repo.get_contents(file.filename, commit.sha)
        print(file.filename)
        print(base64.b64decode(content_file.content).decode())
        print("====================================\n\n\n\n")