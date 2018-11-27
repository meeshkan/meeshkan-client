import meeshkan
import pytest
from pathlib import Path
import tempfile
from tests import __CREDENTIALS_PATH

# Configuration initialized in `tests/__init__.py`
def test_config_init():
    assert meeshkan.config.CONFIG.cloud_url == "http://foo.bar"
    assert meeshkan.config.CREDENTIALS.refresh_token == 'asdf'

def test_credentials_change_with_error():
    non_existing_path = Path(tempfile.gettempdir()).joinpath(next(tempfile._get_candidate_names()))
    with pytest.raises(FileNotFoundError):
        meeshkan.config.Credentials.to_isi("abc", non_existing_path.joinpath(next(tempfile._get_candidate_names())))

def test_credentials_change_no_error():
    original_token = meeshkan.config.CREDENTIALS.refresh_token
    meeshkan.config.Credentials.to_isi("abc", __CREDENTIALS_PATH)
    assert meeshkan.config.Credentials.from_isi(__CREDENTIALS_PATH).refresh_token == "abc"
    meeshkan.config.Credentials.to_isi(original_token, __CREDENTIALS_PATH)
    assert meeshkan.config.Credentials.from_isi(__CREDENTIALS_PATH).refresh_token == original_token