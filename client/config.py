import os
import configparser
import logging
from pathlib import Path
from typing import Optional

import yaml

LOGGER = logging.getLogger(__name__)

PACKAGE_PATH = Path(os.path.dirname(__file__)).joinpath('..')

CONFIG_PATH: Path = PACKAGE_PATH.joinpath('config.yaml')
LOG_CONFIG_FILE: Path = PACKAGE_PATH.joinpath('logging.yaml')

BASE_DIR: Path = Path.home().joinpath('.meeshkan')
JOBS_DIR: Path = BASE_DIR.joinpath('jobs')
LOGS_DIR: Path = BASE_DIR.joinpath('logs')

CREDENTIALS_FILE: Path = BASE_DIR.joinpath('credentials')


def ensure_base_dirs():

    def create_dir_if_not_exist(path: Path):
        if not path.is_dir():
            # Print instead of logging as loggers may not have been configured yet
            print(f"Creating directory {path}")
            path.mkdir()

    create_dir_if_not_exist(BASE_DIR)
    create_dir_if_not_exist(JOBS_DIR)
    create_dir_if_not_exist(LOGS_DIR)


class Configuration:

    def __init__(self, auth_url, cloud_url):
        self.auth_url = auth_url
        self.cloud_url = cloud_url

    @staticmethod
    def from_yaml(path: Path = CONFIG_PATH):
        LOGGER.debug(f"Reading configuration from %s", path)
        if not path.is_file():
            raise FileNotFoundError(f"File {path} not found")
        with path.open('r') as file:
            config = yaml.safe_load(file.read())
        return Configuration(auth_url=config['auth']['url'],
                             cloud_url=config['cloud']['url'])


class Credentials:

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    @staticmethod
    def from_isi(path: Path = CREDENTIALS_FILE):
        LOGGER.debug(f"Reading credentials from %s", path)
        if not path.is_file():
            raise FileNotFoundError(f"Create file {path} first.")
        conf = configparser.ConfigParser()
        conf.read(str(path))
        return Credentials(client_id=conf['auth']['client_id'],
                           client_secret=conf['auth']['client_secret'])


CONFIG: Optional[Configuration] = None
CREDENTIALS: Optional[Credentials] = None


def init(config_path: Path = CONFIG_PATH, credentials_path: Path = CREDENTIALS_FILE):
    global CONFIG, CREDENTIALS  # pylint:disable=global-statement
    if CONFIG is None:
        CONFIG = Configuration.from_yaml(config_path)
    if CREDENTIALS is None:
        CREDENTIALS = Credentials.from_isi(credentials_path)
    return CONFIG, CREDENTIALS
