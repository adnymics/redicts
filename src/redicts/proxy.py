#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main proxy implementation.
"""

# Stdlib:
import json
import operator
import threading

from collections import defaultdict

# External:
import redis
import fakeredis
import six

# Internal:
import redicts.util as util

from redicts._compat import _to_native
from redicts.lock import Lock


# pylint: disable=too-few-public-methods
class _Registry(object):
    """The registry is used to store existing Proxy objects. This is used
    to prevent unneeded re-creating of ValueProxies for the same key.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._proxies = defaultdict(dict)
        self._rconn = None

    def proxy_from_registry(self, path, db_name=None, *args, **kwargs):
        """Check if an existing proxy already exists in the registry,
        if not create a new one with the supplied path.

        This function is thread-safe.

        :param path: (tuple) The tuple representation of a dotted path.
        :param db_name: (str) What redis db to use.
        :param rconn: (redis.Redis) The redis connection to use.
        :returns Proxy: A new or existing
        """
        path_elems = []

        if isinstance(path, six.string_types):
            util.validate_key(path)
            path_elems = path.split(".")
        else:
            # Assume it is iterable or None.
            for elem in path or []:
                util.validate_path_element(elem)
                path_elems.append(elem)

        # Convert to tuple, so path elements stay hashable.
        path_elems_tuple = tuple(path_elems)
        kwargs["db_name"] = db_name

        with self._lock:
            # Prefer the one passed directly.
            return self._proxies[db_name].setdefault(
                path_elems_tuple,
                _Proxy(path_elems_tuple, *args, **kwargs)
            )


# The locking tree is separated form the value tree by a different prefix:
LOCK_TREE_PREFIX = 'l:'
VAL_TREE_PREFIX = 'v:'
_REGISTRY = _Registry()


def _op_proxy(oper):
    """Redirect a python operator to the .val() method of Proxy

    :param oper: (operator) A function that takes
                 two arguments and yields one result.
    :return: The wrapped operator.
    """
    def _operator(self, *args):
        """This function is called instead of the operator in question"""
        return oper(self.val(), *[arg.val() for arg in args])
    return _operator


def _get_sub_keys(conn, full_key):
    """Helper to yield all sub keys including the own key.
    Useful to

    :param conn: (ConnectionPool) Where to get the connection from.
    :param full_key: (str)
    """
    for redis_key in conn.scan_iter(full_key + ".*"):
        yield _to_native(redis_key)

    yield _to_native(full_key)


def _clear_all_locks(rconn):
    """Clear the whole locking tree.
    This function should only be used for unittests.

    :param rconn: (redis.Redis) The connection to redis.
    """
    rconn.delete(LOCK_TREE_PREFIX)
    for redis_key in rconn.scan_iter(LOCK_TREE_PREFIX + ".*"):
        rconn.delete(redis_key)


class _Proxy(object):
    """Proxy object for a single value or a tree of values.
    See the module description for a more detailed description
    and some additional usage examples.
    """
    __slots__ = ["_path", "_redis_lock", "_db_name"]

    def __init__(self, path, lock_acquire_timeout=10,
                 lock_expire_timeout=30, db_name=None):
        """You are not supposed to instance this class yourself.
        Use the provided Proxy(), Section() and Root()

        :param path: (str | iterable) Path to the value.
        :param lock_acquire_timeout: int (seconds)Passed to Lock().
        :param lock_expire_timeout: int (seconds)Passed to Lock().
        :param db_name: (str) Optional db_name to use (uses default otherwise)
        """
        if isinstance(path, six.string_types):
            path = (path, )

        self._path = tuple(path)
        self._db_name = db_name

        self._redis_lock = Lock(
            self._conn(),
            '.'.join((LOCK_TREE_PREFIX, ) + self._path),
            acquire_timeout=lock_acquire_timeout,
            expire_timeout=lock_expire_timeout,
        )

    def _conn(self):
        """Return a pooled connection for the right database"""
        return Pool().get_connection(self._db_name)

    ##########################
    # LOCKING IMPLEMENTATION #
    ##########################

    def is_locked(self):
        """Check if the node or any of its parents are locked"""
        return self._redis_lock.is_locked()

    def acquire(self):
        """Acquire a lock on this value and all of it's children."""
        return self._redis_lock.acquire()

    def release(self):
        """Release a previously acquired lock.

        Note that this does not clear the locks of the children,
        if you locked those explicitly you have to release them.
        """
        return self._redis_lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    ###################################
    # VALUE RETRIEVING IMPLEMENTATION #
    ###################################

    def _get_full_key(self, key=None):
        """Get the fully qualified keypath for this node + key.

        :param key str: The child key to append. If None, the own path
                        will be built.
        :returns str: The fully qualified path of this node.
        """
        if self._path:
            own_key = '.'.join((VAL_TREE_PREFIX, ) + self._path)
        else:
            own_key = VAL_TREE_PREFIX

        if key is not None:
            return own_key + '.' + key

        return own_key

    def key(self):
        """Return the key of this value in redis"""
        return '.'.join(self._path)

    def clear(self):
        """Clear this level of the value tree including all children"""
        for redis_key in _get_sub_keys(self._conn(), self._get_full_key(None)):
            self._conn().delete(redis_key)

    def exists(self):
        """Return true if this value actually exists"""
        return self._conn().exists(self._get_full_key(None)) > 0

    def delete(self, key):
        """Delete an existing key.

        :param key: (str) A dotted path.
        """
        util.validate_key(key)
        self.get(key).clear()

    def iter_children(self):
        """Iterate over all children including and below this node.

        :returns: A generator object, yielding ValueProxies.
        """
        own_path = self._get_full_key(None)
        for redis_key in self._conn().scan_iter(own_path + '.*'):
            # Split the VAL_TREE_PREFIX away, it will be added again when
            # creating a new _Proxy.
            trimmed_key = _to_native(redis_key[len(LOCK_TREE_PREFIX) + 1:])
            yield _REGISTRY.proxy_from_registry(
                trimmed_key, db_name=self._db_name
            )

    def set(self, key, value, expire=None):
        """Set a new value to this key.

        :param key: (str) A dotted path.
        :param value: (object) Any value that can be passed to json.dumps.
        :param expire: (int) Time in seconds when to expire this key or None.
        """
        util.validate_key(key)
        full_key = self._get_full_key(key)

        conn = self._conn()

        # Delete any previous keys since we're overwriting this key.
        # We don't want to have those old keys lying around above.
        util.clear_parents(conn, full_key)

        if isinstance(value, dict):
            # We overwrite all children, clear any leftover keys.
            self.get(key).clear()
            items = util.extract_keys(value, full_key)
        else:
            items = ((full_key, value), )

        # Allow floats as expire time:
        if expire is not None:
            expire = int(expire)

        for full_key, value in items:
            conn.set(full_key, json.dumps(value), ex=expire)

        return self

    def get(self, key):
        """Return a lazy value for this key.

        :param key: (str) A dotted path or simple
        :return: A child Proxy.
        """
        util.validate_key(key)
        child_path = self._path + tuple(key.split('.'))
        return _REGISTRY.proxy_from_registry(child_path, db_name=self._db_name)

    def val(self, default=None):
        """Get the actual value of this proxy"""
        full_key = self._get_full_key(None)

        # Check if this exact key exists. If yes, it's an scalar value.
        # This check will fail if the user set a 'None' value.
        # See below for this case.
        conn = self._conn()
        value = _to_native(conn.get(full_key))
        if value is not None:
            return json.loads(value)

        nested = {}
        for redis_key in conn.scan_iter(full_key + '.*'):
            value = _to_native(conn.get(redis_key))

            # Strip the full key prefix, we're only interested in returning
            # the children values directly.
            sub_key = _to_native(redis_key[len(full_key) + 1:])
            util.feed_to_nested(nested, sub_key, json.loads(value))

        # This is for the case that this key does not exist, or
        # for the case that the user explicitly set a None value.
        if len(nested) is 0:
            # Key really does not exist.
            if default is None and not self.exists():
                return None

            return default

        return nested

    def add(self, count):
        """Convinience function to add a count to this value.
        If the value did not exist yet, it will be set to count.
        Will raise an ValueError if the key exists and does not support
        the add operator.

        :param count: (int) The count to increment.
        :return: The new total count.
        """
        full_key = self._get_full_key()
        new_val = self.val() + count if self.exists() else count
        self._conn().set(full_key, json.dumps(new_val))
        return new_val

    def expire(self, seconds):
        """Expire (i.e. delete) the key after a certain number of seconds.
        After this time .val() will return None and .exists() will return
        False.

        :param seconds: (int) seconds after this value will no longer
                        accessible.
        """
        for redis_key in _get_sub_keys(self._conn(), self._get_full_key(None)):
            self._conn().expire(redis_key, seconds)

    def time_to_live(self):
        """Return the amount of seconds, this value will be accessible.

        :returns int: the amount to live in seconds.
        """
        own_key = self._get_full_key(None)

        try:
            first_redis_key = next(_get_sub_keys(self._conn(), own_key))
            return self._conn().ttl(first_redis_key)
        except StopIteration:
            return None

    # Support dict like access:
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __iter__(self):
        return iter(self.val())

    def __len__(self):
        return len(self.val())

    __eq__ = _op_proxy(operator.eq)
    __ne__ = _op_proxy(operator.ne)
    __lt__ = _op_proxy(operator.lt)
    __gt__ = _op_proxy(operator.gt)
    __le__ = _op_proxy(operator.le)
    __ge__ = _op_proxy(operator.ge)


######################
# CONNECTION POOLING #
######################

def _connection_pool_from_cfg(cfg, db_name=None):
    """Create a new connection pool based on the values found in the config.

    :param cfg (dict): dictionary used to configure the pool details.
    :param db_name (str): Database name to use for connections in this pool.
    :returns redis.BlockingConnectionPool: A new connection pool.
    """
    db_id = cfg.get("database", 0)
    if db_name:
        db_id = cfg.get("names", {}).get(db_name, db_id)

    return redis.BlockingConnectionPool(
        host=cfg.get("host", "localhost"),
        port=cfg.get("port", 6379),
        password=cfg.get("password", None),
        max_connections=cfg.get("max_connections", 100),
        timeout=cfg.get("timeout_secs", 50),
        db=db_id,
    )


@six.add_metaclass(util.Singleton)
class Pool(object):
    """Pool of redis connections"""
    def __init__(self, cfg=None):
        """Create a new pool.

        :param cfg (dict): The config to use for connection details.

            It may have the following keys:

            * host (default: "localhost"): redis host to connect to.
            * port (default: 6379): redis port to connect to.
            * database (default: 0): Default database to use
                                     (if no db_name passed)
            * names (default: {}): Mapping from db name to database index.
            * password (default: None): Password used for connecting.
            * max_connections (default: 100)
            * timeout_secs (default: 50): Timeout passed to redis-py

            If any keys are missing, the default is taken over.
        """
        self._pool_lock = threading.RLock()

        with self._pool_lock:
            self._cfg = cfg or {}
            self._pools = {}
            self._fake_redis = False

    def reload(self, cfg=None, fake_redis=False):
        """Reload the pool, disconnecting previous connections
        and creating a new pool.

        :param cfg (dict): See documentation for __init__.
        """
        with self._pool_lock:
            new_pools = {}
            self._cfg = cfg or {}
            for name, pool in self._pools.items():
                pool.disconnect()
                if fake_redis is False:
                    new_pools[name] = \
                        _connection_pool_from_cfg(self._cfg, name)

            self._pools = new_pools
            self._fake_redis = fake_redis

    def get_connection(self, db_name=None):
        """Get a new (or recycled) connection.
        Note: This function may block if there are too many connections open.

        :return redis.StrictRedis: A new redis connection.
        """
        with self._pool_lock:
            if self._fake_redis:
                return fakeredis.FakeStrictRedis()

            if db_name not in self._pools:
                self._pools[db_name] = \
                    _connection_pool_from_cfg(self._cfg, db_name)

            return redis.StrictRedis(connection_pool=self._pools[db_name])


#######################
# CONVINIENCE METHODS #
#######################


class _ProxyMeta(type):
    """Hack to make Proxy() return a cached instance, although it looks
    and feels like a class instance"""
    def __init__(cls, name, bases, dct):
        super(_ProxyMeta, cls).__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        return _REGISTRY.proxy_from_registry(*args, **kwargs)


class Proxy(six.with_metaclass(_ProxyMeta, _Proxy)):
    """Create a new Proxy.

    :param path str_or_iterable: The path where this value is stored.
            Can be a string (a dotted path) or an iterable of strings.
    :param rconn redis.Redis: Optional; the redis connection to use.
    :returns Proxy: The ready to use Proxy.
    """
    pass


def root(*args, **kwargs):
    """Return the root Proxy"""
    return Proxy(path=(), *args, **kwargs)


def section(name, *args, **kwargs):
    """Convience method for getting a Proxy for a first-level section.
    Try to to use a unique name, otherwise you might overwrite foreign keys.
    A good idiom is to use something like this to get a descriptive, but
    unique name for your module:

        section(__name__)

    :param name str: The section name. May not contain dots.
    :returns: A Proxy for the section.
    """
    return Proxy(path=name, *args, **kwargs)
