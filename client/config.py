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
        return yaml.safe_load(f.read())


def get_secrets(path: Path=CREDENTIALS_PATH):
    logger.info(f"Reading credentials from {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Create file {path} first.")
    conf = configparser.ConfigParser()
    conf.read(str(path))
    return conf
