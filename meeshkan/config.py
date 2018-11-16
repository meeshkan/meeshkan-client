import os
import configparser
import logging
from pathlib import Path
from typing import Optional

import yaml

LOGGER = logging.getLogger(__name__)

PACKAGE_PATH = Path(os.path.dirname(__file__))  # type: Path

CONFIG_PATH = PACKAGE_PATH.joinpath('config.yaml')
LOG_CONFIG_FILE = PACKAGE_PATH.joinpath('logging.yaml')

BASE_DIR = Path.home().joinpath('.meeshkan')
JOBS_DIR = BASE_DIR.joinpath('jobs')
LOGS_DIR = BASE_DIR.joinpath('logs')

CREDENTIALS_FILE = BASE_DIR.joinpath('credentials')


def ensure_base_dirs():

    def create_dir_if_not_exist(path: Path):
        if not path.is_dir():
            # Print instead of logging as loggers may not have been configured yet
            print("Creating directory {path}".format(path=path))
            path.mkdir()

    create_dir_if_not_exist(BASE_DIR)
    create_dir_if_not_exist(JOBS_DIR)
    create_dir_if_not_exist(LOGS_DIR)


class Configuration:

    def __init__(self, cloud_url):
        self.cloud_url = cloud_url

    @staticmethod
    def from_yaml(path: Path = CONFIG_PATH):
        LOGGER.debug("Reading configuration from %s", path)
        if not path.is_file():
            raise FileNotFoundError("File {path} not found".format(path=path))
        with path.open('r') as file:
            config = yaml.safe_load(file.read())
        return Configuration(cloud_url=config['cloud']['url'])


class Credentials:

    def __init__(self, refresh_token):
        self.refresh_token = refresh_token

    @staticmethod
    def from_isi(path: Path = CREDENTIALS_FILE):
        LOGGER.debug("Reading credentials from %s", path)
        if not path.is_file():
            raise FileNotFoundError("Create file {path} first.".format(path=path))
        conf = configparser.ConfigParser()
        conf.read(str(path))
        return Credentials(refresh_token=conf['meeshkan']['token'])


CONFIG = None  # type: Optional[Configuration]
CREDENTIALS = None  # type: Optional[Credentials]


def init(config_path: Path = CONFIG_PATH, credentials_path: Path = CREDENTIALS_FILE):
    global CONFIG, CREDENTIALS  # pylint:disable=global-statement
    if CONFIG is None:
        CONFIG = Configuration.from_yaml(config_path)
    if CREDENTIALS is None:
        CREDENTIALS = Credentials.from_isi(credentials_path)
    return CONFIG, CREDENTIALS
