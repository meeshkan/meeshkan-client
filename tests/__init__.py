"""Initialize configuration from test resources."""
import os
from pathlib import Path
from meeshkan.config import init

__TEST_RESOURCES_PATH = Path(os.path.dirname(__file__)).joinpath('resources')
__CONFIG_PATH = __TEST_RESOURCES_PATH.joinpath('config.yaml')
__CREDENTIALS_PATH = __TEST_RESOURCES_PATH.joinpath('.credentials')

init(config_path=__CONFIG_PATH, credentials_path=__CREDENTIALS_PATH)
