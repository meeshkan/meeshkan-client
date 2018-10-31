import client
from client.config import get_secrets, get_config
from pathlib import Path


def test_config():
    config = get_config(path=str(Path.cwd().joinpath('tests', 'resources', 'config.yaml')))
    assert config['auth']['url'] == "meeshkan.eu.auth0.com"
    assert config['cloud']['url'] == "http://localhost:4000"


def test_secrets():
    secrets = get_secrets(path=Path.cwd().joinpath('tests', 'resources', '.credentials'))
    assert secrets['auth']['client_id'] == 'asdf'
    assert secrets['auth']['client_secret'] == 'Qwerty'
