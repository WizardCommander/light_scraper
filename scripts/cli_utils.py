"""Shared CLI utilities for parser scripts."""

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_filename: str, verbose: bool = False):
    """Configure logging with file and console handlers.

    Args:
        log_filename: Name of the log file (e.g., 'price_list_parser_{time}.log')
        verbose: If True, set console logging to DEBUG level
    """
    # Remove default handler
    logger.remove()

    # Add file handler (DEBUG level, rotated daily)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / log_filename,
        rotation="1 day",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )

    # Add console handler (INFO or DEBUG level)
    console_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=console_level,
        format="<level>{level: <8}</level> | {message}",
        colorize=True,
    )
