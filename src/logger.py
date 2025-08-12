"""Logging configuration for SCP Wiki Tag Translator."""

import logging
import sys


def setup_logger(name: str = "scp_tag_translator", level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with console handler.

    Args:
        name: Logger name
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    if logger.handlers:
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: [LEVEL] message
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# Default logger instance
logger = setup_logger()
