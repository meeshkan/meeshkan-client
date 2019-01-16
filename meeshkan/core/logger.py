import logging
import logging.config
from pathlib import Path
from typing import List

import yaml

from .config import LOG_CONFIG_FILE, LOGS_DIR

LOGGER = logging.getLogger(__name__)

# Do not expose anything by default (internal module)
__all__ = []  # type: List[str]


def setup_logging(log_config: Path = LOG_CONFIG_FILE, silent: bool = False):
    """Setup logging configuration
    This MUST be called before creating any loggers.
    """

    if not log_config.is_file():
        raise RuntimeError("Logging file {log_file} not found".format(log_file=log_config))

    with log_config.open() as log_file:
        config_orig = yaml.safe_load(log_file.read())

    def prepare_filenames(config):
        """
        Prepend `LOGS_DIR` to all 'filename' attributes listed for handlers in logging.yaml
        :param config: Configuration dictionary
        :return: Configuration with 'filename's prepended with LOGS_DIR
        """
        for handler_name in config['handlers'].keys():
            handler_config = config['handlers'][handler_name]
            if 'filename' in handler_config:
                filename = Path(handler_config['filename']).name
                handler_config['filename'] = str(LOGS_DIR.joinpath(filename))
        return config

    config = prepare_filenames(config_orig)
    logging.config.dictConfig(config)
    if silent:
        remove_non_file_handlers()


def remove_non_file_handlers():
    log = logging.getLogger()  # Root logger
    for handler in log.handlers.copy():
        if not isinstance(handler, logging.FileHandler):
            log.handlers.remove(handler)
    LOGGER.info("Deleted non-file handlers from logging")
