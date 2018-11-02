import os
import logging
import logging.config
import logging.handlers
import yaml


def setup_logging(default_path='logging.yaml', default_level=logging.INFO):
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
    log = logging.getLogger()  # Root logger
    log.info("Deleting stream handlers from logging")
    for handler in log.handlers.copy():
        if not isinstance(handler, logging.FileHandler):
            log.handlers.remove(handler)
