import meeshkan
import pytest
from pathlib import Path
import tempfile

# Configuration initialized in `tests/__init__.py`
def test_config_init():
    assert meeshkan.config.CONFIG.cloud_url == "http://foo.bar"
    assert meeshkan.config.CREDENTIALS.refresh_token == 'asdf'

def test_credentials_change_with_error():
    non_existing_path = Path(tempfile.gettempdir()).joinpath(next(tempfile._get_candidate_names()))
    with pytest.raises(FileNotFoundError):
        meeshkan.config.Credentials.to_isi("abc", non_existing_path.joinpath(next(tempfile._get_candidate_names())))

def test_credentials_change_no_error():
    fid, tmp = tempfile.mkstemp()
    tmpfile = Path(tmp)
    meeshkan.config.Credentials.to_isi("abc", tmpfile)
    assert meeshkan.config.Credentials.from_isi(tmpfile).refresh_token == "abc"