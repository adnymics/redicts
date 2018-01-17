#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This module implements a redis backed storage for arbitary temporary values.

The store works hierarchically. Acessing values works by using a dotted path
notation (e.g: root.child1.child2.value). This allows natural splitting up the
values in sections. Getting "root.child1" will yield a dict that contains a
subdict under "child2" which contains the actual value under the "value" key.
Instead of actually returning these values though, a new Proxy is
returned, on which .val() can be called to lazily retrieve the actual value.
You can store every value which you can also pass to json.dumps().

Locking is also possible hierarchically by calling acquire()/release() on each
Proxy anywhere in the hierarchy. If a parent Proxy is already locked,
a recursive lock will be added on the parent.

ATTENTION: Note that Proxy operations are by default *not* locked.  Always
call acquire() before or use it in combination with the `with` statement.

The locking implementation (Lock) is separated and can be used
on it's own if you need a threadsafe lock that also spans over more than
once process. It is likely a better alternative to RedisLock from TempStorage,
since this one is not threadsafe. However, it's about 50% slower.

See the docstrings for more details.

Basic usage example:

.. code-block:: python

    >>> with section("QualityControl") as sec:
    ...     sec["value"] = 23
    ...     sec["subsection"] = {"a": 42}
    ...     sec["value"].val()  # => 23
    ...     sec["subsection.a"].val()  # => 42
    ...     sec["subsection"]["a"].val()  # => 42
    ...
    >>> # Accessing the subsection directly works fine too.
    >>> with section("QualityControl.subsection") as sub:
    ...     sub["a"].val()  # => 23


..codeauthor:: c.pahl@adnymics.com
"""

__version__ = '1.0.0'


# pylint: disable=unused-import
from redicts.proxy import section, root, Pool, Proxy
from redicts.lock import Lock
from redicts.errors import LockTimeout, InternalError
