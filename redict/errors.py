#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Errors used throughout the library.
"""


class LockTimeout(Exception):
    """Raised when lock creation fails within the timeout"""
    pass


class InternalError(Exception):
    """Raised when the implementation got confused.
    This should only happen when somebody else tampers with the locking
    keys in redis.
    """
    pass
