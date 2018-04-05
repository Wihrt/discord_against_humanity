#!/usr/bin/env python
# coding: utf-8

from logging import getLogger
from functools import wraps

LOGGER = getLogger(__name__)

def async_log_event(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        LOGGER.debug("Calling %s.%s, Args %s, Kwargs %s" % (func.__class__.__name__, func.__name__, args, kwargs))
        result = await func(*args, **kwargs)
        if result is not None:
            LOGGER.debug("Result %s.%s : %s" % (func.__class__.__name__, func.__name__, result))
        return result
    return wrapper
