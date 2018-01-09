#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
General utils, mostly for handling dotted key paths.
"""

# Stdlib:
import os
import threading

# External:
import six

# Internal:
from redicts.errors import InternalError


def validate_key(key):
    """Check if an key is a valid dotted path

    :raises: ValueError if invalid.
    """
    if len(key) is 0:
        raise ValueError("Key or a part of it may not be empty")

    if key.startswith('.') or key.endswith('.'):
        raise ValueError(
            "Key may not start or end with a single dot: {}".format(
                key
            )
        )

    if '..' in key:
        raise ValueError(
            "Key may not contain successive double dots: {}".format(
                key
            )
        )


def validate_path_element(elem):
    """Check if a single path element is valid.

    :param elem: (str) A part of an dotted path (no dots allowed)
    :raises: ValueError if invalid.
    """
    if len(elem) is 0:
        raise ValueError("Path elements may not be empty")

    if '.' in elem:
        raise ValueError("Path elements should contain no dot")


def build_key_hierarchy(key):
    """Build a list with key in it and all of it's parent keys.

    :param key: (str) A dotted path.
    :returns [str]: A list of keys.
    """
    all_keys = [key]
    try:
        while True:
            key = key[:key.rindex('.')]
            all_keys.append(key)
    except ValueError:
        pass

    return all_keys


def build_lock_token(count):
    """Build the lock token to identify what a lock is protecting.

    The token consists out of the pid, current thread id and a counter
    that indicates the number of locks hold on this resource.

    :param count: (int) The lock count.
    :return str: The built token.
    """
    return '{p}:{t}:{c}'.format(
        p=os.getpid(),
        t=threading.current_thread().ident,
        c=count
    )


def parse_lock_token(token):
    """Parse a lock token into pid, thread id and lock count.

    :param token: (str) Token (hopefully) built by _build_lock_token.
    :return tuple: pid, thread_ident and lock_count.
    """
    splitted = token.split(":", 2)
    if len(splitted) != 3:
        raise InternalError("Bad token: {}".format(token))

    return [int(elem) for elem in splitted]


def extract_keys(nested, prefix=""):
    """Flatten the (potentially nested) dict `nested`
    by extracting each leaf node. Each leaf is identified by a dotted path.

    :param nested: (dict) The dict to extract keys from.
    :param prefix: (str) The prefix which every yielded dotted key should have.
    :returns iter: An iterator that yields tuples of (dotted_key, value)
    """
    for key, value in nested.items():
        if not isinstance(key, six.string_types):
            raise ValueError("Keys must always be strings")

        redis_key = prefix + '.' + key if prefix else key
        if isinstance(value, dict):
            for sub in extract_keys(value, prefix=redis_key):
                yield sub
        else:
            yield redis_key, value


def feed_to_nested(nested, full_key, value):
    """Feed a dotted path (key) with a certain value to a dictionary.
    If the path contains dots, the result will be a nested dict.

    :param nested: (dict) The dict to fill the values in.
                        Existing values will be overwritten.
    :param full_key: (str) A dotted path.
    :param value: Any value.
    """
    keys = full_key.split(".")
    curr = nested
    last = keys.pop()

    for key in keys:
        # Make sure that more nested keys will overwrite values along the way.
        # Setting these keys should not yield a TypeError for example:
        #   1) a.b.c = 2
        #   2) a.b.c.d = {"x": 3}
        if isinstance(curr.get(key), dict) is False:
            curr[key] = curr = {}
        else:
            curr = curr.setdefault(key, {})

    curr[last] = value


def clear_parents(rconn, key):
    """Clear all parent keys of self.

    :param rconn: (redis.Redis) The connection to redis.
    :param key: (str) Dotted path of which node's parent to clear.
    """
    parents = build_key_hierarchy(key)
    for parent in parents[1:]:
        rconn.delete(parent)


class Singleton(type):
    """Singleton metaclass.

    Shamelessly stolen from SO:
    https://stackoverflow.com/questions/31875/is-there-a-simple-elegant-way-to-define-singletons
    """
    def __init__(cls, name, bases, dct):
        super(Singleton, cls).__init__(name, bases, dct)
        cls.instance = None

    def __call__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls.instance


