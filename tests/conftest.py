import pytest

from redict import Pool


@pytest.fixture
def fake_redis():
    Pool().reload(fake_redis=True)
    conn = Pool().get_connection()
    conn.flushall()
    return conn


@pytest.fixture
def real_redis():
    Pool().reload(fake_redis=False)
    conn = Pool().get_connection()
    conn.flushall()
    return conn
