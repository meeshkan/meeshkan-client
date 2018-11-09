from pathlib import Path

import meeshkan
import meeshkan.config
from meeshkan.config import init


def test_config_init():
    assert meeshkan.config.CONFIG.auth_url == "meeshkan.eu.auth0.com"
    assert meeshkan.config.CONFIG.cloud_url == "http://localhost:4000"
    assert meeshkan.config.CREDENTIALS.client_id == 'asdf'
    assert meeshkan.config.CREDENTIALS.client_secret == 'Qwerty'
