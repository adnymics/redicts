#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test the Proxy implementation using fakeredis.
No integration tests (i.e. real redis server) allowed here.
"""

# Stdlib:
import time
import threading

# External:
import pytest

# Internal:
from redicts import Proxy, root, section


# pylint: disable=no-self-use,attribute-defined-outside-init,unused-argument


@pytest.mark.unittest
def test_basic_set(fake_redis):
    """See if the very basic testcases work"""
    root_prox = Proxy(path=('TestQualityControl',))
    root_prox.clear()

    root_prox.set('a', 2)
    assert root_prox.get('a').val() == 2

    root_prox.set('a.b', 3)
    assert root_prox.get('a.b').val() == 3
    assert root_prox.get('a').val() == {'b': 3}

    root_prox.set('a.c', None)
    assert root_prox.get('a.c').val() is None
    assert root_prox.get('a').val() == {'b': 3, 'c': None}

    root_prox.set('a', {'b': 42, 'e': 3})
    assert root_prox.get('a').val() == {'b': 42, 'e': 3}


@pytest.mark.unittest
def test_locking_edge_cases(fake_redis):
    """See if locking edge cases like recursive locks work"""
    root_prox = Proxy(path=('QualityControl',))
    root_prox.clear()

    assert not root_prox.is_locked()

    # This should work for the same thread:
    with root_prox:
        assert root_prox.is_locked()
        with root_prox:
            assert root_prox.is_locked()

    assert not root_prox.is_locked()

    # See if the lock is released when an exception happens
    # inside the with block.
    with pytest.raises(KeyError):
        with root_prox:
            raise KeyError("Inside job")

    assert not root_prox.is_locked()


@pytest.mark.unittest
def test_recursive_local_lock(fake_redis):
    """Test if a local value can be modified by the same thread,
    but blocks when being accessed from more than one.
    """
    root_prox = Proxy(path=('QualityControl',))
    root_prox.clear()

    thread_died_yet = False

    def _lock_in_thread():
        """The root_prox lock shoud block until it was released"""
        with root_prox:
            # This timeout here is to make sure thread_died_yet was set.
            time.sleep(0.05)
            assert thread_died_yet

    with root_prox:
        # Spin up a thread and see if it blocks as expected.
        thr = threading.Thread(target=_lock_in_thread)
        thr.start()
        thr.join(0.25)

        # This flag is needed since _lock_in_thread will (rightfully)
        # acquire the lock once this context manager left.
        thread_died_yet = True

    time.sleep(0.5)


def test_root_proxy(fake_redis):
    """See if the root proxy is set and gettable"""
    with root() as root_prox:
        root_prox.clear()
        root_prox["x"] = 2
        assert root_prox["x"].val() == 2


@pytest.mark.unittest
def test_section_proxy(fake_redis):
    """See if the section helper works"""
    with section("QualityConytrol") as sec:
        sec.clear()
        sec["x"] = 2
        assert sec["x"].val() == 2


@pytest.mark.unittest
def test_basic_locking(fake_redis):
    """Check if single process locking works"""
    root_prox = Proxy(path=('QualityControl',))
    root_prox.clear()

    root_prox.acquire()
    assert root_prox.is_locked()
    root_prox.set('child', {})
    root_prox.release()


@pytest.mark.unittest
def test_nested_locking(fake_redis):
    """Check if locking is possible """
    sec = section("nested")
    sec.clear()

    sec['a.b.c.d'] = 10

    # Locking this will work (since locks are recursive here)
    sec['a.b'].acquire()
    sec['a.b.c'].acquire()

    checks = {
        "thread-died": False
    }

    def _lock_me_dead():
        """This should block, so thread_died_yet should be True
        since it's set after the join timeout.
        """
        with sec['a.b.c.d']:
            time.sleep(0.05)

        checks["thread-died"] = True

    thr = threading.Thread(target=_lock_me_dead)
    thr.start()
    thr.join(0.5)

    # If the lock would not block, the join would give the thread
    # enough time to set the flag.
    assert checks['thread-died'] is False

    # Release the top node.
    sec['a.b'].release()

    # Thread should still not be able to acquire the lock
    # since a.b.c was locked (which locked a.b in turn)
    assert checks['thread-died'] is False
    time.sleep(0.1)
    assert checks['thread-died'] is False

    sec['a.b.c'].release()

    # Now finally the thread should be able to acquire the lock.
    time.sleep(0.5)
    assert checks['thread-died'] is True


@pytest.mark.unittest
def test_sequential_lock(fake_redis):
    """
    Simply test if incrementing a value locking in a single thread
    works (other tests always test concurrent access)
    """
    locked_val = Proxy('LockMe').set("x", 0)
    for _ in range(1000):
        with locked_val:
            locked_val.set("x", locked_val.get("x").val() + 1)


@pytest.mark.unittest
def test_same_reference(fake_redis):
    """Test if the same reference is returned for the same proxy path."""
    assert Proxy("x") is Proxy("x")
    assert Proxy("x") is not Proxy("y")


@pytest.mark.unittest
def test_if_equal(fake_redis):
    """See if __eq__ works as expected"""
    Proxy("section").set("x", 1)
    Proxy("section").set("y", 1)

    assert Proxy("section.x") == Proxy("section.y")
    Proxy("section").set("y", 2)
    assert Proxy("section.x") != Proxy("section.y")


@pytest.mark.unittest
def test_delete(fake_redis):
    """Check if the delete key method works"""
    root_prox = root()
    root_prox.set("x", 42)
    assert root_prox.get("x").val() == 42

    root_prox.delete("x")
    assert root_prox.get("x").val() is None


@pytest.mark.unittest
def test_value_exists(fake_redis):
    """Test if the exists method works."""
    sec = section("dummy")

    assert not sec["x"].exists()
    sec["x"] = 42
    assert sec["x"].exists()


@pytest.mark.unittest
def test_iter_children(fake_redis):
    """See if getting all children (only leaf nodes!) work"""
    sec = section("dummy")
    sec.clear()

    sec.set("a.b.c", 2)
    sec.set("a.b.d", 3)

    children = [(prx.key(), prx.val()) for prx in sec.iter_children()]

    assert children == [('dummy.a.b.c', 2), ('dummy.a.b.d', 3)]
    assert fake_redis.get('v:.dummy.a.b.c') == b'2'
    assert fake_redis.get('v:.dummy.a.b.d') == b'3'


@pytest.mark.unittest
def test_add(fake_redis):
    """See if adding on a key works"""
    sec = section("dummy")
    sec.clear()

    assert sec.get("x").val() is None
    sec.get("x").add(1)
    assert sec.get("x").val() == 1
    sec.get("x").add(1)
    assert sec.get("x").val() == 2


@pytest.mark.unittest
def test_val_default(fake_redis):
    """Test if the default param of val() works"""
    sec = section("dummy")
    sec.clear()

    assert sec["x"].val() is None
    assert sec["x"].val(default=1) is 1
    assert sec["x"].val(default=None) is None

    sec["x"] = 10
    assert sec["x"].val(default=1) is 10
    assert sec["x"].val(default=None) is 10


@pytest.mark.unittest
def test_timeout(fake_redis):
    """See if the timeout is set correctly (regression test)"""
    sec = section("t", lock_acquire_timeout=0, lock_expire_timeout=-1)
    # pylint: disable=protected-access
    assert sec._redis_lock._acquire_seconds == 1
    # pylint: disable=protected-access
    assert sec._redis_lock._expire_seconds == 1

    sec = section("y")
    # pylint: disable=protected-access
    assert sec._redis_lock._acquire_seconds == 10
    # pylint: disable=protected-access
    assert sec._redis_lock._expire_seconds == 30
