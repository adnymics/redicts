#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fixtures to setup tests.
"""

import pytest

from redicts import Pool


@pytest.fixture
def fake_redis():
    """Fixture to run a test with a fakeredis (in-memory) connection"""
    Pool().reload(fake_redis=True)
    conn = Pool().get_connection()
    conn.flushall()
    return conn


@pytest.fixture
def real_redis():
    """Fixture to run a test with a full connection to redis"""
    Pool().reload(fake_redis=False)
    conn = Pool().get_connection()
    conn.flushall()
    return conn
