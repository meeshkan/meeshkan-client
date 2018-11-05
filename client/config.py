import os
import configparser
import logging
from pathlib import Path

import yaml

LOGGER = logging.getLogger(__name__)
CONFIG_PATH: Path = Path(os.path.dirname(__file__)).joinpath('..', 'config.yaml')
CREDENTIALS_PATH: Path = Path.home().joinpath('.meeshkan', 'credentials')

CONFIG = None
SECRETS = None


def init(config_path=CONFIG_PATH, credentials_path=CREDENTIALS_PATH):
    global CONFIG, SECRETS  # pylint:disable=global-statement
    if CONFIG is None:
        CONFIG = get_config(config_path)
    if SECRETS is None:
        SECRETS = get_secrets(credentials_path)


def get_config(path: Path = CONFIG_PATH):
    if not path.is_file():
        raise FileNotFoundError(f"File {path} not found")
    with path.open('r') as f:
        return yaml.safe_load(f.read())


def get_secrets(path: Path = CREDENTIALS_PATH):
    LOGGER.info(f"Reading credentials from {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Create file {path} first.")
    conf = configparser.ConfigParser()
    conf.read(str(path))
    return conf
