:orphan:

Welcome to asgi-tools's documentation!
======================================

|Product| -- Is a really lightweight ASGI_ Toolkit to build ASGI applications
faster.

The Features:

* All popular async python libraries are supported (Asyncio_, Trio_, Curio_);
* Competitive Performance;
* HTTP Headers/Cookies/Form data support (:class:`~asgi_tools.Request`);
* HTTP (:class:`~asgi_tools.Response`), Static files (:class:`~asgi_tools.ResponseFile`), Streaming (:class:`~asgi_tools.ResponseStream`) responses;
* WebSocket (:class:`~asgi_tools.ResponseWebSocket`) support;
* ASGI Lifespan support (:class:`~asgi_tools.LifespanMiddleware`) with startup and shutdown events;
* ASGI Routing support (:class:`~asgi_tools.RouterMiddleware`) to route your handlers by http urls;
* Auto parsing for app responses (:class:`~asgi_tools.ResponseMiddleware`);
* Test client (:class:`~asgi_tools.tests.ASGITestClient`) to test ASGI_ applications;
* And more

.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _Asyncio: https://docs.python.org/3/library/asyncio.html
.. _Trio: https://trio.readthedocs.io/en/stable/index.html

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

Welcome to the documentation. Get started with :doc:`installation` and then get
an overview with the :doc:`usage`. The rest of the docs describe each component
of :mod:`~asgi_tools` in detail, with a full reference in the :doc:`api`
section.

User's Guide
------------

.. toctree::
   :maxdepth: 2

   installation
   usage

API Reference
-------------

If you are looking for information on a specific function, class or
method, this part of the documentation is for you.

.. toctree::
   :maxdepth: 4

   api



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |Product| replace:: :py:mod:`ASGI-Tools`
