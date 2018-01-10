.. image:: https://github.com/adnymics/redicts/raw/master/docs/logo.svg
    :width: 55%

A utilty package to save arbitary nested python dicts and objects in redis.

|rtd| |nbsp| |coverage| |nbsp| |travis|

.. |rtd| image:: https://readthedocs.org/projects/redicts/badge/?version=latest

.. TODO: Setup.
.. |coverage| unicode:: 0xA0

.. TODO: Setup.
.. |travis| unicode:: 0xA0

.. |nbsp| unicode:: 0xA0
   :trim:

Usage
=====

This package can be used to save arbitary values in a hierarchy. Each element
of this hierarchy is referenced by a dotted path like this: ``a.b.c``. When
saving a nested dictionary, it's nested contents automatically get translated
to such a dotted path by it's string keys:

.. code-block:: python

    # `23` can be read by specifying the path "a.b.c":
    {
        "a": {
            "b": {
                "c": 23
            }
        }
    }

A special feature of this package is concurrent access: It can be safely used
from more than one process. The locking implementation is also separated and
can be used on it's one if desirable. Also, the implementation is clever enough
to not require a global lock if changes are done in different parts of the
hierarchy.

You can store every object in ``redicts`` that works with ``json.dumps()``.

Documentation
=============

Documentation can be found on readthedocs:

    http://redicts.readthedocs.io/en/latest

Example
=======

If redis is started with default host/port/password, this should work:

.. code-block:: pycon

    >>> from redicts import Section
    >>> with Section("a.b.c") as sec:
    ...     #  Setting values:
    ...     sec["my-value"] = 42
    ...     sec["my-part"] = {"key": "value"}
    ...
    ...     # Reading values:
    ...     sec["my-value"].val()     # => 42
    ...     sec["my-part.key"].val()  # => "value"
