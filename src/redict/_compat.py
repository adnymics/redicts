#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Stdlib:
import sys

# External:
import six


def _to_native(x, charset=sys.getdefaultencoding(), errors='strict'):
    if x is None or isinstance(x, str):
        return x

    if six.PY3:
        return x.decode(charset, errors)
    return x.encode(charset, errors)
