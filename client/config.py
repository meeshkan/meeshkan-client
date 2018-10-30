import os
import yaml
import configparser
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def creds_path():
    return Path.home().joinpath('.meeshkan', 'credentials')


def get_config(path='config.yaml'):
    if not os.path.isfile(path):
        raise FileNotFoundError("File {} not found".format(path))
    with open(path, 'rt') as f:
        config = yaml.safe_load(f.read())
    return config


def get_secrets():
    credentials_path = creds_path()
    logger.info("Reading credentials from {}".format(str(credentials_path)))
    if not credentials_path.is_file():
        raise FileNotFoundError("Create file {}".format(credentials_path))
    config = configparser.ConfigParser()
    config.read(str(credentials_path))
    return config
