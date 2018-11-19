import meeshkan
import meeshkan.config


# Configuration initialized in `tests/__init__.py`
def test_config_init():
    assert meeshkan.config.CONFIG.cloud_url == "http://foo.bar"
    assert meeshkan.config.CREDENTIALS.refresh_token == 'asdf'
