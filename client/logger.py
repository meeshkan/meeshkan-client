import os
import logging
import logging.config
import logging.handlers
import yaml

LOGGER = logging.StreamHandler


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


def remove_stream_handlers():
    log = logging.getLogger()  # Root logger
    log.info("Deleting stream handlers from logging")
    to_remove = []
    for handler in log.handlers[:]:
        log.info(handler)
        if not isinstance(handler, logging.handlers.RotatingFileHandler):
            to_remove.append(handler)
    for handler in to_remove:
        log.removeHandler(handler)

    for handler in log.handlers[:]:
        log.info("Remaining %s", type(handler))