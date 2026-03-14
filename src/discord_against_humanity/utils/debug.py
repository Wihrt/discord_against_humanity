"""Async logging decorator for debugging."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def async_log_event(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that logs async function calls and their return values.

    Args:
        func: The async function to wrap.

    Returns:
        The wrapped function with logging.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger.debug(
            "Calling %s.%s, Args %s, Kwargs %s",
            getattr(func, "__qualname__", func.__name__),
            func.__name__,
            args,
            kwargs,
        )
        result = await func(*args, **kwargs)
        if result is not None:
            logger.debug(
                "Result %s.%s: %s",
                getattr(func, "__qualname__", func.__name__),
                func.__name__,
                result,
            )
        return result

    return wrapper
