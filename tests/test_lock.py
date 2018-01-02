#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
import threading

from redict import Lock


def test_single_thread_acquire(redis_conn):
    mtx = Lock(redis_conn, 'dum-dum')
    assert not mtx.is_locked()

    mtx.acquire()
    assert mtx.is_locked()

    mtx.release()
    assert not mtx.is_locked()

    with mtx:
        assert mtx.is_locked()

    assert not mtx.is_locked()


def test_acquire_timeout(redis_conn):
    """Test if a threaded double acquire actually blocks"""
    mtx = Lock(redis_conn, 'dum-dum', acquire_timeout=1)

    checks = {
        "raised_timeout": False
    }

    with mtx:
        def _wait_for_timeout():
            """Wait until timeout"""
            try:
                with mtx:
                    pass
            except Lock.LockTimeout:
                checks["raised_timeout"] = True

        thr = threading.Thread(target=_wait_for_timeout)
        thr.start()
        thr.join(1.5)

    # The lock should be destroyed now.
    assert redis_conn.get('dum-dum') is None
    assert checks["raised_timeout"]


def test_acquire_expire(redis_conn):
    """Test if the expire feature works"""
    mtx = Lock(redis_conn, 'dum-dum', expire_timeout=1)
    mtx.acquire()

    # This is only a dict to make it
    # possible to modify it in another thread.
    checks = {
        "thread_acquired": False,
        "thread_released": False
    }

    def wait_for_expire():
        """Wait until the key is expire and acquire then"""
        mtx.acquire()
        checks["thread_acquired"] = True
        mtx.release()
        checks["thread_released"] = True

    thr = threading.Thread(target=wait_for_expire)
    thr.start()

    # Key expires in 1 second, wait for it.
    time.sleep(1.5)
    mtx.release()
    thr.join(0.1)

    assert redis_conn.get('dum-dum') is None
    assert checks["thread_acquired"]
    assert checks["thread_released"]
