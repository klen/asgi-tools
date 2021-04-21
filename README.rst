.. image:: https://raw.githubusercontent.com/klen/asgi-tools/develop/.github/assets/asgi-tools.png
   :height: 100

.. _description:

**asgi-tools** -- Is a really lightweight ASGI_ Toolkit to build ASGI applications faster.

.. _badges:

.. image:: https://github.com/klen/asgi-tools/workflows/tests/badge.svg
    :target: https://github.com/klen/asgi-tools/actions
    :alt: Tests Status

.. image:: https://github.com/klen/asgi-tools/workflows/docs/badge.svg
    :target: https://klen.github.io/asgi-tools
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: PYPI Version

.. image:: https://img.shields.io/pypi/pyversions/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: Python Versions

----------

.. _documentation:

**Documentation is here**: https://klen.github.io/asgi-tools

ASGI-Tools is designed to be used as an ASGI Toolkit to quickly build really
lightweight ASGI applications/middlewares/tools.

For instance these middlewares were built with the library:

* `ASGI-Sessions <https://github.com/klen/asgi-sessions>`_
* `ASGI-Babel <https://github.com/klen/asgi-babel>`_
* `ASGI-Prometheus <https://github.com/klen/asgi-prometheus>`_

.. _features:

**Features:**

- Supports all most popular async python libraries: `Asyncio`_, `Trio`_ and Curio_
- `Request`_                 -- Parse ASGI scope, get url, headers, cookies, read a request's data/json/form-data
- `Response`_                -- Send HTTP (text, html, json, stream, sse, file, http errors) responses
- `ResponseWebsocket`_       -- Work with websockets
- `RequestMiddleware`_       -- Parse a scope and insert the parsed request into the scope
- `ResponseMiddleware`_      -- Parse responses and convert them into ASGI messages
- `RouterMiddleware`_        -- Route HTTP requests
- `LifespanMiddleware`_      -- Process a lifespan cycle
- `StaticFilesMiddleware`_   -- Serve static files from URL prefixes
- `asgi_tools.tests.TestClient <https://klen.github.io/asgi-tools/api.html#testclient>`_ -- A test client with websockets support to test asgi applications
- `App`_                     -- A simple foundation for ASGI apps

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. note:: pypy3 is also supported

**ASGI-Tools** belongs to the category of ASGI_ web frameworks, so it requires
an ASGI HTTP server to run, such as uvicorn_, daphne_, or hypercorn_.

.. _installation:

Installation
=============

**asgi-tools** should be installed using pip: ::

    pip install asgi-tools

A Quick Example
===============

You can use any of ASGI-Tools components independently.

Dispite this ASGI-Tools contains App_ helper to quickly build ASGI
applications. For instance:

Save this to ``app.py``.

.. code-block:: python

    from asgi_tools import App

    app = App()

    @app.route('/')
    async def hello(request):
        return "Hello World!"

Run it with `uvicorn`

.. code-block:: sh

   $ uvicorn app:app


.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/klen/asgi-tools/issues

.. _contributing:

Contributing
============

Development of the project happens at: https://github.com/klen/asgi-tools

.. _license:

License
========

Licensed under a `MIT license`_.


.. _links:

.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _Asyncio: https://docs.python.org/3/library/asyncio.html
.. _Curio: https://curio.readthedocs.io/en/latest/
.. _MIT license: http://opensource.org/licenses/MIT
.. _Trio: https://trio.readthedocs.io/en/stable/index.html
.. _klen: https://github.com/klen
.. _uvicorn: http://www.uvicorn.org/ 
.. _daphne: https://github.com/django/daphne/
.. _hypercorn: https://pgjones.gitlab.io/hypercorn/

.. _Request: https://klen.github.io/asgi-tools/api.html#request
.. _Response: https://klen.github.io/asgi-tools/api.html#responses
.. _ResponseWebSocket: https://klen.github.io/asgi-tools/api.html#responsewebsocket
.. _RequestMiddleware: https://klen.github.io/asgi-tools/api.html#requestmiddleware
.. _ResponseMiddleware: https://klen.github.io/asgi-tools/api.html#responsemiddleware
.. _LifespanMiddleware: https://klen.github.io/asgi-tools/api.html#lifespanmiddleware
.. _StaticFilesMiddleware: https://klen.github.io/asgi-tools/api.html#staticfilesmiddleware
.. _RouterMiddleware: https://klen.github.io/asgi-tools/api.html#routermiddleware
.. _App: https://klen.github.io/asgi-tools/api.html#application
