Example Usage
=============

Instead of boring you with an insanely long description of what this library is
capable of, we'll keep it short and just give you examples. You'll learn the
concepts along the way. All details also can be found in the
:ref:`api_reference`.

Basics
------

Getting and setting values
~~~~~~~~~~~~~~~~~~~~~~~~~~

All values in ``redis`` are accessed by instances of the
:py:class:`redicts.Proxy`. class. They represent a key that points to a value
and can be asked to fetch it with :py:class:`redicts.Proxy.val`:

.. code-block:: pycon

    >>> from redicts import Proxy, root
    >>> p = Proxy("a.b.c")
    >>> p.set("d", 42)
    >>> p.get("d").val()
    42
    # set() also returns a proxy for the current value:
    >>> p.set("x", {"y": "z"}).val()
    {'x': {'y': 'z'}, 'd': 42}
    >>> root().val()
    {'a': {'b': {'c': {'x': {'y': 'z'}, 'd': 42}}}}
    >>> # Not exsting values will yield None.
    >>> root().get("who?").val()
    None

Also observe that the values really live a hierarchy.

.. warning::

    Note that value access is not locked by default for performance reasons!
	Take a look at the next example to allow concurrent access.

Concurrent access to values
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every :py:class:`redicts.Proxy` can be locked against concurrent access with
it's :py:class:`redicts.Proxy.acquire` and :py:class:`redicts.Proxy.release`
methods. This is optional, since locking can eat quite a bit of performance
when done often. Take this example:

.. code-block:: python

    from redicts import Proxy
    from multiprocessing import Process


    Proxy("a.b.c").set("d", 0)

    def increment():
        for _ in range(10000):
            with Proxy("a.b.c") as prox:
                prox.get("d").add(1)

    p = Process(target=increment)
    p.start()
    increment()
    p.join()


Try this example without the ``with`` to see the difference.

Other useful operations
~~~~~~~~~~~~~~~~~~~~~~~

Here are a few operations you can do on a :py:class:`redicts.Proxy`:

- :py:meth:`redicts.Proxy.iter_children`: Return a :py:class:`redicts.Proxy`: for each direct child.
- :py:meth:`redicts.Proxy.delete`: Delete a single subkey.
- :py:meth:`redicts.Proxy.exists`: Check if a key has a value assigned.
- :py:meth:`redicts.Proxy.clear`: Clear everthing below this prox.

Here they are in action:

.. code-block:: pycon

    >>> from redicts import Pool, root
    >>> r = root()
    >>> r.set('x', 1)
    >>> r.set('y', {"z": 2})
    >>> r.val()
    {'y': {'z': 2}, 'x': 1}
    >>> list(r)
    >>> ["y", "x"]
    >>> {p.key(): p.val() for p in root().iter_children()}
    {'y.z': 2, 'x': 1}
    >>> r.get("x").exists()
    True
    >>> r.delete("x")
    >>> r.get("x").exists()
    False
    >>> r.clear()
    >>> r.get("y").exists()
    False

Different redis server
~~~~~~~~~~~~~~~~~~~~~~

Everything related to connection details can be configured via the :py:class:`redicts.Pool`
singleton. It's responsible for keeping a pool of open connections and acts as
central instance for configurations. Upon first use of anything network related
:py:class:`redicts.Pool` is instantiated with default connection details. If you like to use
different connection details you can do this:

.. code-block:: python

    from redicts import Pool, root

    Pool().reload(cfg=dict(
        host="localhost",
        port=6379,
        database=0,
        password="1234",
        max_connections=100,
        timeout_secs=50,
    ))

Using ``fakredis``
~~~~~~~~~~~~~~~~~~

Using a real instance of ``redis`` can be inconvinient for testing.
In this case you can setup your tests with ``fakeredis``:

.. code-block:: python

    from redicts import Pool, root

    # Make sure to use `fakeredis`
    Pool().reload(fake_redis=True)

    # clear everything that was written by this library:
    root().clear()

Advanced
--------

Not all of the following features might be required during »daily« usage.

Using more than one database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you'd like to use more than one database you can setup a mapping in the beginning:

.. code-block:: python

    from redicts import Pool, Proxy

    # Assuming default setup:
    Pool().reload(cfg={
        "default": 0,
        "names": {
            "persons": 1,
            "things": 2,
        }
    })

    # Later on you can use the human readable name for your database:
    # All three values are stored in different redis db with different values.
    Proxy("x").set("y", 1)
    Proxy("x", db_name="persons").set("y", 2)
    Proxy("x", db_name="things").set("y", 3)

Time to live
~~~~~~~~~~~~

You can tell ``redis`` to expire keys after some time. This is also possible with :py:mod:`redicts`:

.. code-block:: python

    import time
    from redicts import Pool, root

    # Expire this key in 10 seconds:
    root().set("x", "still here!", expire=10)
    time.sleep(1)
    root().get("x").time_to_live()  # => 9
    root().get("x").val()           # => "still here!"
    time.sleep(10)
    root().get("x").time_to_live()  # => -2
    root().get("x").val()           # => None

    # You can also alternatively set the expire time later:
    root().set("x", "still here!")
    root().get("x").expire(10)
