#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Compatibility helpers.
"""

# Stdlib:
import sys

# External:
import six


def _to_native(val, charset=sys.getdefaultencoding(), errors='strict'):
    """Convery a unicode (py2.7) or bytes (py3) to a str without hassle."""
    if val is None or isinstance(val, str):
        return val

    if six.PY3:
        return val.decode(charset, errors)
    return val.encode(charset, errors)
