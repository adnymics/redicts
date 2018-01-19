.. image:: https://cdn.rawgit.com/adnymics/redicts/ebd9808f/docs/logo.svg
    :width: 55%


A utility package to save arbitrary nested Python dicts and objects in Redis.

|rtd| |nbsp| |travis| |nbsp| |coverage| |nbsp| |pypi| |nbsp| |pep8| |nbsp| |gplv3|

.. |rtd| image:: https://readthedocs.org/projects/redicts/badge/?version=latest
   :target: http://redicts.readthedocs.io/en/latest/

.. |coverage| image:: https://coveralls.io/repos/github/adnymics/redicts/badge.svg
   :target: https://coveralls.io/github/adnymics/redicts

.. |travis| image:: https://travis-ci.org/adnymics/redicts.svg?branch=master
    :target: https://travis-ci.org/adnymics/redicts

.. |pypi| image:: https://badge.fury.io/py/redicts.svg
    :target: https://badge.fury.io/py/redicts

.. |pep8| image:: https://img.shields.io/badge/code%20style-pep8-green.svg
    :target: https://www.python.org/dev/peps/pep-0008

.. |gplv3| image:: https://img.shields.io/badge/License-GPL%20v3-green.svg
    :target: https://www.gnu.org/licenses/gpl-3.0

.. |nbsp| unicode:: 0xA0
   :trim:

Usage
=====

This package can be used to save arbitrary values in a hierarchy. Each element
of this hierarchy is referenced by a dotted path like this: ``a.b.c``. When
saving a nested dictionary, its nested contents automatically get translated
to such a dotted path by its string keys:

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
can be used on its own if desirable. Also, the implementation is clever enough
to not require a global lock if changes are done in different parts of the
hierarchy.

You can store every object in ``redicts`` that works with ``json.dumps()``.

Why?
====

We use ``redis`` quite a lot in our day-to-day work and often want to share
values between different (micro-)services. This package helps us to do that
safely and easily.

Documentation
=============

Documentation can be found on ReadTheDocs:

    http://redicts.readthedocs.io/en/latest

Example
=======

If redis is started with default host/port/password, this should work:

.. code-block:: pycon

    >>> from redicts import section
    >>> with section("a.b.c") as sec:
    ...     #  Setting values:
    ...     sec["my-value"] = 42
    ...     sec["my-part"] = {"key": "value"}
    ...
    ...     # Reading values:
    ...     sec["my-value"].val()     # => 42
    ...     sec["my-part.key"].val()  # => "value"
