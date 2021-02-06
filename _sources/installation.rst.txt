Installation
============

Python Version
--------------

We recommend using the latest version of Python. **ASGI-Tools** supports Python
3.7 and newer.


Dependencies
------------

These distributions will be installed automatically when installing
**ASGI-Tools**.

* `Http-Router`_ implements HTTP routing.
* `Yarl`_ implements URL parsing
* `Multidict`_ implements a dict-like collection of key-value pairs where key
  might be occurred more than once in the container.  templates to avoid
  injection attacks.

.. _Http-Router: https://github.com/klen/http-router
.. _Yarl: https://palletsprojects.com/p/jinja/
.. _Multidict: hhttps://github.com/aio-libs/multidict


Install **ASGI-Tools**
----------------------

Use the following command to install:

.. code-block:: sh

    $ pip install asgi-tools

You'll also want to install an ASGI_ server, such as `Uvicorn`_, `Daphne`_, or `Hypercorn`_:

.. code-block:: sh

    $ pip install uvicorn

.. _Uvicorn: https://github.com/encode/uvicorn
.. _Daphne: https://github.com/django/daphne
.. _Hypercorn: https://gitlab.com/pgjones/hypercorn/

**ASGI-Tools** is now installed. Check out the :doc:`/usage` or go to the
:doc:`Documentation Overview </index>`.

.. Links

.. _ASGI: https://asgi.readthedocs.io/en/latest/
