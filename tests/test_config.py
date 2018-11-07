from pathlib import Path

import client
import client.config
from client.config import init


def test_config_init():
    assert client.config.CONFIG.auth_url == "meeshkan.eu.auth0.com"
    assert client.config.CONFIG.cloud_url == "http://localhost:4000"
    assert client.config.CREDENTIALS.client_id == 'asdf'
    assert client.config.CREDENTIALS.client_secret == 'Qwerty'
