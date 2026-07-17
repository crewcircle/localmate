import asyncio
import functools
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


def retry_on_failure(
    max_retries: int = 2,
    delay: float = 5.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Decorator factory that retries a function on failure.

    Args:
        max_retries: Maximum number of retries after the initial attempt.
        delay: Seconds to sleep between retries.
        exceptions: Tuple of exception types to catch and retry on.

    Returns:
        A decorator that wraps the target function with retry logic.
        Works for both synchronous and asynchronous functions.
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt == max_retries:
                            logger.error(
                                "%s failed after %d attempt(s): %s",
                                func.__name__,
                                max_retries + 1,
                                e,
                            )
                            raise
                        logger.warning(
                            "%s attempt %d/%d failed, retrying in %.1fs: %s",
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            delay,
                            e,
                        )
                        await asyncio.sleep(delay)
                raise last_exc  # pragma: no cover — unreachable

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exc = e
                        if attempt == max_retries:
                            logger.error(
                                "%s failed after %d attempt(s): %s",
                                func.__name__,
                                max_retries + 1,
                                e,
                            )
                            raise
                        logger.warning(
                            "%s attempt %d/%d failed, retrying in %.1fs: %s",
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            delay,
                            e,
                        )
                        import time

                        time.sleep(delay)
                raise last_exc  # pragma: no cover — unreachable

            return sync_wrapper

    return decorator
