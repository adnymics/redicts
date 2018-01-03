API Reference
=============

This documentation is generated from the docstrings found in the source.

Main Interface
---------------

.. autoclass:: redicts.Proxy
    :members:
    :inherited-members:

.. autofunction:: redicts.root

.. autofunction:: redicts.section

.. autoclass:: redicts.Pool
    :members:

Locking
-------

The locking implementation is available as separte class and can be used as
multiprocess lock.

.. autoclass:: redicts.Lock
   :members:

Exceptions
----------

.. autoexception:: redicts.InternalError

.. autoexception:: redicts.LockTimeout
