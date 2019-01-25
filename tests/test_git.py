import pytest
from unittest import mock
from pathlib import Path
import shutil
import os

from .utils import TempCredentialsFile, wait_for_true

import meeshkan
from meeshkan.core.service import Service
import meeshkan.git.utils as mg

CLIENT_REPO = "Meeshkan/meeshkan-client"
FIRST_VERSION_COMMIT = "cee35e9"  # v0.0.1 psuedo-release
FIRST_OFFICIAL_RELEASE_BRANCH = "release-v-0.1.0"  # first official release


@pytest.fixture
def clean():
    def remove_tempdir_from_gitrunner(gitrunner: mg.GitRunner):
        shutil.rmtree(gitrunner.target_dir)
    return remove_tempdir_from_gitrunner


def test_git_verify():
    git_exists = False
    def fake_which(*args, **kwargs):
        return "fake_address" if git_exists else None

    with mock.patch("shutil.which", fake_which):
        with pytest.raises(mg.GitRunner.GitException):
            mg.GitRunner._verify_git_exists()
        git_exists = True
        mg.GitRunner._verify_git_exists()


def test_git_access_token():
    with TempCredentialsFile(refresh_token="fake") as tmpfile:
        with pytest.raises(mg.GitRunner.GitException):
            mg.GitRunner._git_access_token(tmpfile.file), "Default test credentials do not contain a github token!"
        tmpfile.update(git_token="abc")
        assert mg.GitRunner._git_access_token(tmpfile.file) == "abc"


def test_gitrunner_init(clean):
    repo = "foobar"
    gitrunner = mg.GitRunner(repo=repo)
    git_token = meeshkan.config.CREDENTIALS.git_access_token
    try:
        assert gitrunner.url == "https://{token}:x-oauth-basic@github.com/{repo}".format(token=git_token, repo=repo)
    finally:
        clean(gitrunner)


def test_gitrunner_pull_branch(clean):
    gitrunner = mg.GitRunner(repo=CLIENT_REPO)
    gitrunner.pull_repo(branch=FIRST_OFFICIAL_RELEASE_BRANCH)
    version_fname = os.path.join(gitrunner.target_dir, "meeshkan/__version__.py")
    try:
        assert os.path.isfile(version_fname)
        with open(version_fname) as version_fd:
            assert version_fd.read() == "__version__ = '0.1.0'\n"
    finally:
        clean(gitrunner)


def test_gitrunner_pull_commit(clean):
    gitrunner = mg.GitRunner(repo=CLIENT_REPO)
    gitrunner.pull_repo(commit_sha=FIRST_VERSION_COMMIT)
    version_fname = os.path.join(gitrunner.target_dir, "client/__version__.py")
    try:
        assert os.path.isfile(version_fname)
        with open(version_fname) as version_fd:
            assert version_fd.read() == "__version__ = \"0.0.1\"", "Commit SHA is expected to reset to matching version"
    finally:
        clean(gitrunner)


def test_gitrunner_pull_branch_and_commit(clean):
    gitrunner = mg.GitRunner(repo=CLIENT_REPO)
    gitrunner.pull_repo(branch=FIRST_OFFICIAL_RELEASE_BRANCH, commit_sha=FIRST_VERSION_COMMIT)
    version_fname = os.path.join(gitrunner.target_dir, "client/__version__.py")
    try:
        assert os.path.isfile(version_fname)
        with open(version_fname) as version_fd:
            assert version_fd.read() == "__version__ = \"0.0.1\"", "When pulling a commit and a branch, commit SHA is" \
                                                                   " expected to take precedence!"
    finally:
        clean(gitrunner)
