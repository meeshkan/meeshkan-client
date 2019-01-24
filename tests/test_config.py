import meeshkan
import pytest
from pathlib import Path
import tempfile

# Configuration initialized in `tests/__init__.py`
def test_config_init():
    assert meeshkan.config.CONFIG.cloud_url == "http://foo.bar", "Configuration should match yaml file contents"
    assert meeshkan.config.CREDENTIALS.refresh_token == 'asdf', "Credentials should match yaml file contents"
    assert meeshkan.config.CREDENTIALS.git_access_token is None, "By default no git access token is supplied"


def test_credentials_change_with_error():
    imaginary_path = Path(tempfile.gettempdir()).joinpath(next(tempfile._get_candidate_names()))
    with pytest.raises(FileNotFoundError):
        meeshkan.config.Credentials.to_isi("abc", path=imaginary_path.joinpath(next(tempfile._get_candidate_names())))


def test_credentials_change_no_error():
    _, tmp = tempfile.mkstemp()
    tmpfile = Path(tmp)
    refresh_token = "abc"
    git_token = "def"
    assert_msg1 = "Credentials should match newly created file with `to_isi` and " \
                  "refresh token '{}'".format(refresh_token)
    assert_msg2 = "Credentials should match newly created file with `to_isi` and " \
                  "git token '{}'".format(git_token)
    try:
        meeshkan.config.Credentials.to_isi(refresh_token, git_token=git_token, path=tmpfile)
        assert meeshkan.config.Credentials.from_isi(tmpfile).refresh_token == refresh_token, assert_msg1
        assert meeshkan.config.Credentials.from_isi(tmpfile).git_access_token == git_token, assert_msg2
    finally:
        tmpfile.unlink()  # Cleanup


def test_credentials_change_without_git():
    _, tmp = tempfile.mkstemp()
    tmpfile = Path(tmp)
    refresh_token = "abc"
    git_token = "def"
    new_refresh_token = "def"
    assert_msg1 = "Git credentials should be maintained if not provided in `to_isi`"
    assert_msg2 = "Refresh token should be updated if provided in `to_isi`"
    try:
        meeshkan.config.Credentials.to_isi(refresh_token, git_token=git_token, path=tmpfile)
        meeshkan.config.Credentials.to_isi(new_refresh_token, path=tmpfile)
        assert meeshkan.config.Credentials.from_isi(tmpfile).git_access_token == git_token, assert_msg1
        assert meeshkan.config.Credentials.from_isi(tmpfile).refresh_token == new_refresh_token, assert_msg2
    finally:
        tmpfile.unlink()


def test_credentials_changes_without_token():
    _, tmp = tempfile.mkstemp()
    tmpfile = Path(tmp)
    refresh_token = "abc"
    git_token = "def"
    new_git_token = "def"
    assert_msg1 = "Refresh token should be maintained if not provided in `to_isi`"
    assert_msg2 = "Git credentials should be updated if provided in `to_isi`"
    try:
        meeshkan.config.Credentials.to_isi(refresh_token, git_token=git_token, path=tmpfile)
        meeshkan.config.Credentials.to_isi(git_token=new_git_token, path=tmpfile)
        assert meeshkan.config.Credentials.from_isi(tmpfile).git_access_token == new_git_token, assert_msg1
        assert meeshkan.config.Credentials.from_isi(tmpfile).refresh_token == refresh_token, assert_msg2
    finally:
        tmpfile.unlink()
