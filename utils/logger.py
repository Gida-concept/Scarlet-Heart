# utils/logger.py

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.settings import LOG_LEVEL

# Directory for log files
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Formatter for all handlers
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
formatter = logging.Formatter(LOG_FORMAT)

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance with both console and rotating file handlers.
    Ensures handlers are only added once per logger.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    # Set base level
    logger.setLevel(LOG_LEVEL.upper())

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL.upper())
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating file handler
    log_file = LOG_DIR / "bot.log"
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(LOG_LEVEL.upper())
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Avoid duplicate logs in root
    logger.propagate = False

    return logger