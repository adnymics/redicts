#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test the key related utils.
"""

# External:
import pytest

# Internal:
from redicts.util import \
    extract_keys, feed_to_nested, validate_key, parse_lock_token, InternalError


SAMPLE_DATA = {
    "a": {
        "b": 2,
        "c": {
            "d": 9,
            "e": {
                "f": 42,
            }
        }
    },
    "g": 3
}

FLATTENED_DATA = {
    ('a.c.e.f', 42),
    ('a.c.d', 9),
    ('a.b', 2),
    ('g', 3),
}


@pytest.mark.unittest
def test_extract_keys():
    """See if extracting all keys from a dict works"""
    assert set(extract_keys({})) == set([])
    key_values = set(extract_keys(SAMPLE_DATA))
    assert key_values == FLATTENED_DATA


@pytest.mark.unittest
def test_feed_to_nested():
    """See if converting the keys back to dicts seems to work"""
    nested = {}
    for key, value in FLATTENED_DATA:
        feed_to_nested(nested, key, value)

    assert nested == SAMPLE_DATA

    feed_to_nested(nested, "a.c.e", 2)
    feed_to_nested(nested, "a.c.e.f", {"deep": "nested"})
    assert nested["a"]["c"]["e"]["f"]["deep"] == "nested"


@pytest.mark.unittest
def test_validate_key():
    """Try some invalid keys"""
    with pytest.raises(ValueError):
        validate_key("")

    with pytest.raises(ValueError):
        validate_key(".a")

    with pytest.raises(ValueError):
        validate_key("a.")

    with pytest.raises(ValueError):
        validate_key("a..b")

    validate_key("a.b")


@pytest.mark.unittest
def test_parse_lock_token():
    """See if passing good & wrong lock tokens work"""
    pid, ident, count = parse_lock_token("1:2:3")
    assert pid == 1
    assert ident == 2
    assert count == 3

    with pytest.raises(InternalError):
        parse_lock_token("1:2")
