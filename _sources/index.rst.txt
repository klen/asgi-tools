:orphan:

ASGI-Tools Documentation
=========================

Lightweight, high-performance ASGI toolkit for modern Python async apps.

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

Overview
--------

**ASGI-Tools** is a minimal, extensible ASGI_ toolkit designed to help you build async Python applications faster and more efficiently.

Key Features
------------

* **Async Support** – Seamless integration with Asyncio_, Trio_, and Curio_
* **High Performance** – Optimized for speed and minimal resource usage
* **Rich Request Handling** – Powerful :class:`~asgi_tools.Request` supporting headers, cookies, forms, and file uploads
* **Flexible Responses** – Multiple response types: HTTP, static files, streaming, SSE, WebSocket via :class:`~asgi_tools.Response`
* **Built-in Middleware** – Essential middleware for common patterns:
    * :class:`~asgi_tools.RequestMiddleware` – Request parsing
    * :class:`~asgi_tools.ResponseMiddleware` – Response handling
    * :class:`~asgi_tools.RouterMiddleware` – URL routing
    * :class:`~asgi_tools.LifespanMiddleware` – Application lifecycle
    * :class:`~asgi_tools.StaticFilesMiddleware` – Static file serving
* **Testing Support** – Built-in test client with WebSocket support via :class:`~asgi_tools.tests.ASGITestClient`
* **Simple Application Builder** – Quick-start with :class:`~asgi_tools.App`

Installation
------------

Install ASGI-Tools with pip:

.. code-block:: sh

    pip install asgi-tools

Quick Start
-----------

Here's a minimal example to get you started:

.. code-block:: python

    from asgi_tools import App

    app = App()

    @app.route("/")
    async def hello(request):
        return "Hello, World!"

Run it with an ASGI server like uvicorn_:

.. code-block:: sh

    uvicorn app:app

Visit http://127.0.0.1:8000/ to see your application running!

Documentation Overview
-----------------------

* :doc:`installation` – Install and set up ASGI-Tools
* :doc:`usage` – Learn how to use ASGI-Tools effectively
* :doc:`api` – Detailed API reference

User's Guide
------------

.. toctree::
   :maxdepth: 2

   installation
   usage

API Reference
-------------

For detailed information on functions, classes, and methods:

.. toctree::
   :maxdepth: 2

   api

Contributing
------------

ASGI-Tools is an open source project. Contributions, issues, and feature requests are welcome!

* GitHub: https://github.com/klen/asgi-tools
* Report Issues: https://github.com/klen/asgi-tools/issues

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _Asyncio: https://docs.python.org/3/library/asyncio.html
.. _Trio: https://trio.readthedocs.io/en/stable/index.html
.. _Curio: https://github.com/dabeaz/curio
.. _uvicorn: http://www.uvicorn.org/
