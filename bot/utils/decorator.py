#!/usr/bin/env python
# coding: utf-8

from logging import getLogger

LOGGER = getLogger(__name__)

def log_event(func):
    def wrapper(*args, **kwargs):
        LOGGER.debug("Calling %s.%s, Args %s, Kwargs %s" % (func.__class__.name, func.__name__, args, kwargs))
        result = func(*args, **kwargs)
        if result is not None:
            LOGGER.debug("Result %s.%s : %s" % (func.__class__.name, func.__name__, result))
        return result
    return wrapper

