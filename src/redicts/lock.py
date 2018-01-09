#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Optimistic, distribured lock implementation.
"""

# Stdlib:
import os
import time
import threading

# External:
import redis

# Internal:
import redicts.util as util

from redicts._compat import _to_native
from redicts.errors import LockTimeout, InternalError


class Lock(object):
    """Implement a distributed, thread-safe lock for redis.

    The basics are described here: https://redis.io/topics/transactions
    This lock is more flexible than other locking implementations, since
    it supports tree-based locking by specifying a dotted path as key.

    If you lock an element higher up in the hierarchy, all elements below it
    will be automatically locked too. It is still possible to lock elements
    below though, but those will only add their lock to the lock above.

    This implementation uses optimistic locking, i.e. retry if some of the
    to be locked values changed.
    """
    __slots__ = ["_key", "_redis_conn", "_expire_seconds", "_acquire_seconds"]

    def __init__(self, redis_conn, key, expire_timeout=30, acquire_timeout=10):
        # Note: This object may not have any state (counter, etc.)
        # in order to stay thread-safe. The redis connection is thread-safe.
        util.validate_key(key)

        self._key = key
        self._redis_conn = redis_conn
        self._expire_seconds = max(1, expire_timeout)
        self._acquire_seconds = max(1, acquire_timeout)

    def _find_root_lock(self, callback, pipe, keys):
        """Find out which parent node to lock. Take self if none is locked."""
        # Abort this operation immediately if some of the keys
        # we are looking at changes compared to now.
        pipe.watch(*keys)

        # See if any lock in the tree above us is already locked.
        for key in keys:
            if pipe.get(key) is not None:
                # This key was locked by someone.
                # Try to acquire lock on this (might also be our own one)
                result = callback(pipe, key)
                break
        else:
            # No key locked yet. Just lock our own key.
            result = callback(pipe, self._key)

        pipe.execute()
        return result

    def _find_root_lock_with_retries(self, callback):
        """Find out which parent node to lock, but retry indefinitely if
        any of the involved data changed on the remote side.
        If the correct node could have been determined, call callback
        to do some actual work on it.
        """
        keys = util.build_key_hierarchy(self._key)
        with self._redis_conn.pipeline() as pipe:
            while True:
                try:
                    return self._find_root_lock(callback, pipe, keys)
                except redis.WatchError:
                    # One of the watched keys changed:
                    # Bad luck, try again.
                    continue

    def _acquire(self, pipe, key):
        """Actual implementation of acquire(), called by _find_root_lock

        :param pipe: (redis.StrictPipe) A redis pipe.
        :param key: (str) The full key to lock.
        """
        retries = self._acquire_seconds * 20
        lock_count = 0

        own_pid = os.getpid()
        own_thread_ident = threading.current_thread().ident

        while retries > 0:
            lock_token = _to_native(pipe.get(key))

            # Does this lock even exist?
            if lock_token is None:
                break

            # Is it maybe one of our own locks?
            pid, thread_ident, lock_count = util.parse_lock_token(lock_token)
            if pid == own_pid and thread_ident == own_thread_ident:
                break

            # Cannot lock now. Wait a short time before a retry.
            time.sleep(0.05)
            retries -= 1

        if retries is 0:
            raise LockTimeout(
                "Lock timed out after {} retries".format(
                    self._acquire_seconds * 20
                )
            )

        # Take over and make sure the key expires at some time.
        # Also increment the lock count.
        pipe.multi()
        pipe.set(key, util.build_lock_token(lock_count + 1))
        if self._expire_seconds is not None:
            pipe.expire(key, self._expire_seconds)

    def _release(self, pipe, key):
        """Actual implementation of release(), called by _find_root_lock

        :param pipe: (redis.Pipe) A redis pipe.
        :param key: (str) The full key to release.
        """
        lock_token = _to_native(pipe.get(key))
        if lock_token is None:
            # This lock token does not exist anymore. This either means
            # it expired (okay) or release was called without prior acquire
            # (which is pretty bad). We can't really tell, so just return.
            return

        # We could also check if pid and thread_ident is the same as own,
        # but that might fail on edge cases where the key expired and
        # another pid/thread got the lock (validly). We don't check here
        # since we cannot know for sure.
        _, _, lock_count = util.parse_lock_token(lock_token)

        pipe.multi()

        # These exceptions are supposed to uncover errors in locking logic.
        if lock_count <= 0:
            raise InternalError(
                "Negative or zero lock count ({}) for {} ({})".format(
                    lock_count, key, self
                )
            )

        if lock_count == 1:
            # Remove the key; we're not locking it anymore.
            pipe.delete(key)
        else:
            # We held an recursive lock. Leave our mark.
            pipe.set(key, util.build_lock_token(lock_count - 1))
            if self._expire_seconds is not None:
                pipe.expire(key, self._expire_seconds)

    def is_locked(self):
        """Return True if this lock was already acquired by someone"""
        def _is_locked(pipe, key):
            """Actual implementation of is_locked"""
            lock_value = _to_native(pipe.get(key))
            return lock_value is not None

        return self._find_root_lock_with_retries(_is_locked)

    def acquire(self):
        """Acquire the lock and wait if needed"""
        return self._find_root_lock_with_retries(self._acquire)

    def release(self):
        """Release the lock again"""
        return self._find_root_lock_with_retries(self._release)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_exc):
        self.release()
