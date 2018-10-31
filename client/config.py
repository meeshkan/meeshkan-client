import os
import yaml
import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
CREDENTIALS_PATH: Path = Path.home().joinpath('.meeshkan', 'credentials')


def get_config(path='config.yaml'):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File {path} not found")
    with open(path, 'rt') as f:
        config = yaml.safe_load(f.read())
    return config


def get_secrets():
    logger.info(f"Reading credentials from {CREDENTIALS_PATH}")
    if not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(f"Create file {CREDENTIALS_PATH} first.")
    config = configparser.ConfigParser()
    config.read(str(CREDENTIALS_PATH))
    return config
