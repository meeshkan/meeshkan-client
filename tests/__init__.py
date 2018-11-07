"""Initialize configuration from test resources."""
from pathlib import Path
from client.config import init

__TEST_RESOURCES_PATH = Path.cwd().joinpath('tests', 'resources')
__CONFIG_PATH = __TEST_RESOURCES_PATH.joinpath('config.yaml')
__CREDENTIALS_PATH = __TEST_RESOURCES_PATH.joinpath('.credentials')

init(config_path=__CONFIG_PATH, credentials_path=__CREDENTIALS_PATH)
