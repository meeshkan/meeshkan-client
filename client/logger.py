import logging
import logging.config
from pathlib import Path

import yaml

import client.config

LOGGER = logging.getLogger(__name__)


def setup_logging(log_config: Path = client.config.LOG_CONFIG_FILE):
    """Setup logging configuration
    This MUST be called before creating any loggers.
    """

    if not log_config.is_file():
        raise RuntimeError(f"Logging file {log_config} not found")

    with log_config.open() as log_file:
        config_orig = yaml.safe_load(log_file.read())

    def prepare_filenames(config):
        """
        Prepend `client.config.LOGS_DIR` to all 'filename' attributes listed for handlers in logging.yaml
        :param config: Configuration dictionary
        :return: Configuration with 'filename's prepended with LOGS_DIR
        """
        for handler_name in config['handlers'].keys():
            handler_config = config['handlers'][handler_name]
            if 'filename' in handler_config:
                filename = Path(handler_config['filename']).name
                handler_config['filename'] = str(client.config.LOGS_DIR.joinpath(filename))
        return config

    config = prepare_filenames(config_orig)
    logging.config.dictConfig(config)


def remove_non_file_handlers():
    LOGGER.info("Deleting non-file handlers from logging")
    log = logging.getLogger()  # Root logger
    for handler in log.handlers.copy():
        if not isinstance(handler, logging.FileHandler):
            log.handlers.remove(handler)
