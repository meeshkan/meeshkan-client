import os
import logging
import logging.config
import yaml


LOGGER = logging.getLogger(__name__)


def setup_logging(default_path='logging.yaml'):
    """Setup logging configuration
    This MUST be called before creating any loggers.
    """
    path = default_path
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        logging.config.dictConfig(config)
    else:
        raise RuntimeError(f"Logging file {path} not found")


def remove_non_file_handlers():
    LOGGER.info("Deleting non-file handlers from logging")
    log = logging.getLogger()  # Root logger
    for handler in log.handlers.copy():
        if not isinstance(handler, logging.FileHandler):
            log.handlers.remove(handler)
