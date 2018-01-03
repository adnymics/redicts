#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test the key related utils.
"""

# External:
import pytest

# Internal:
from redict.util import _extract_keys, _feed_to_nested


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
    assert set(_extract_keys({})) == set([])
    key_values = set(_extract_keys(SAMPLE_DATA))
    assert key_values == FLATTENED_DATA


@pytest.mark.unittest
def test_feed_to_nested():
    """See if converting the keys back to dicts seems to work"""
    nested = {}
    for key, value in FLATTENED_DATA:
        _feed_to_nested(nested, key, value)

    assert nested == SAMPLE_DATA

    _feed_to_nested(nested, "a.c.e", 2)
    _feed_to_nested(nested, "a.c.e.f", {"deep": "nested"})
    assert nested["a"]["c"]["e"]["f"]["deep"] == "nested"
