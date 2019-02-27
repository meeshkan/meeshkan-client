import os
import logging
from pathlib import Path
from typing import Optional, List

LOGGER = logging.getLogger(__name__)

PACKAGE_PATH = Path(os.path.dirname(__file__))  # type: Path

CONFIG_PATH = PACKAGE_PATH.joinpath('config.yaml')
LOG_CONFIG_FILE = PACKAGE_PATH.joinpath('logging.yaml')

BASE_DIR = Path.home().joinpath('.meeshkan')
JOBS_DIR = BASE_DIR.joinpath('jobs')
LOGS_DIR = BASE_DIR.joinpath('logs')

CREDENTIALS_FILE = BASE_DIR.joinpath('credentials')

CONFIG = None  # type: Optional[Configuration]
CREDENTIALS = None  # type: Optional[Credentials]


# Don't automatically expose anything to top level, as the entire module is loaded as-is
__all__ = []  # type: List[str]


del logging  # Clean-up (only leaves Path available in this module)
del os
del List


def ensure_base_dirs(verbose=True):

    def create_dir_if_not_exist(path: Path):
        if not path.is_dir():
            # Print instead of logging as loggers may not have been configured yet
            if verbose:
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
        import yaml

        LOGGER.debug("Reading configuration from %s", path)
        if not path.is_file():
            raise FileNotFoundError("File {path} not found".format(path=path))
        with path.open('r') as file:
            config = yaml.safe_load(file.read())
        return Configuration(cloud_url=config['cloud']['url'])


class Credentials:
    def __init__(self, refresh_token, git_access_token):
        self.refresh_token = refresh_token
        if not git_access_token:
            git_access_token = None  # Make sure we write None on values such as "", False, None, etc
        self.git_access_token = git_access_token

    @staticmethod
    def from_isi(path: Path = CREDENTIALS_FILE):
        """
        Read credentials from file.
        :param path: Path from where to read credentials.
        :raises FileNotFoundError: If path does not exist.
        :return: Credentials.
        """
        import configparser

        LOGGER.debug("Reading credentials from %s", path)
        if not path.is_file():
            raise FileNotFoundError("Create file {path} first.".format(path=path))
        conf = configparser.ConfigParser()
        conf.read(str(path))
        return Credentials(refresh_token=conf.get('meeshkan', 'token', fallback=""),  # type: ignore
                           git_access_token=conf.get('github', 'token', fallback=""))  # type: ignore

    @staticmethod
    def to_isi(refresh_token: Optional[str] = None, git_access_token: Optional[str] = None,
               path: Path = CREDENTIALS_FILE):
        """
        Creates the credential file with given refresh token, git_access_token token or both.
        Overrides each previous token if exists.
        Assumes that `path` can be written with `path.open("w")`, i.e., that the parent directory exists.

        :param refresh_token: New refresh_token or None
        :param git_access_token: New git_access_token or None
        :param path: Path where to write credentials. If exists, used also to read previous credentials.
        :return:
        """
        try:
            prev_creds = Credentials.from_isi(path)  # Restore from previous if not some arguments are not supplied
            git_access_token = git_access_token or prev_creds.git_access_token
            refresh_token = refresh_token or prev_creds.refresh_token
        except FileNotFoundError:
            pass

        if not git_access_token:
            if refresh_token is None:
                raise ValueError("Nothing to write to ISI file.")
            git_access_token = ""  # Make sure we write an empty string if no git_token is given

        with path.open("w") as credential_file:
            credential_file.write("[meeshkan]\ntoken={token}\n".format(token=refresh_token))
            credential_file.write("\n[github]\ntoken={token}\n".format(token=git_access_token))
            credential_file.flush()


def init_config(config_path: Path = CONFIG_PATH, credentials_path: Path = CREDENTIALS_FILE, force_refresh=False):
    """Allows a one-time initialization of CONFIG and CREDENTIALS."""
    global CONFIG, CREDENTIALS  # pylint:disable=global-statement
    if CONFIG is None or force_refresh:
        CONFIG = Configuration.from_yaml(config_path)
    if CREDENTIALS is None or force_refresh:
        CREDENTIALS = Credentials.from_isi(credentials_path)
    return CONFIG, CREDENTIALS


del Optional
