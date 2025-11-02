"""Retry logic with exponential backoff.

Following CLAUDE.md: prefer pure, testable functions over classes.
"""

import time
from typing import Callable, TypeVar
from loguru import logger

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
) -> T:
    """Execute function with exponential backoff retry logic.

    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        max_delay: Maximum delay between retries in seconds

    Returns:
        Result of successful function execution

    Raises:
        Exception: Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retry attempts failed: {e}")
                raise

            delay = min(base_delay * (exponential_base**attempt), max_delay)
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    raise last_exception  # Should never reach here, but makes type checker happy
