.. redicts documentation master file, created by
   sphinx-quickstart on Tue Jan  2 10:28:21 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to redicts's documentation!
===================================

A utility package to save arbitrary nested Python dicts and objects in Redis.

.. image:: ../logo.svg
    :width: 55%

This package can be used to save arbitrary values in a hierarchy. Each element
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

.. toctree::
   :maxdepth: 2

   install.rst
   examples.rst
   api.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
