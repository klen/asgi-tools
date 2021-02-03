.. image:: https://raw.githubusercontent.com/klen/asgi-tools/develop/.github/assets/asgi-tools.png
   :height: 100
   :width: 100


ASGI-Tools
##########

.. _description:

**asgi-tools** -- Is a toolkit to build ASGI applications faster

.. _badges:

.. image:: https://github.com/klen/asgi-tools/workflows/tests/badge.svg
    :target: https://github.com/klen/asgi-tools/actions
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: PYPI Version

.. image:: https://img.shields.io/pypi/pyversions/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: Python Versions

.. _features:

**Features:**

- Supports `Asyncio`_ and `Trio`_ libraries
- ``Request``                 -- Parse ASGI scope, get url, headers, cookies, read a request's data/json/form-data
- ``Response``                -- Send HTTP (text, html, json, stream, file, http errors) responses
- ``ResponseWebsocket``       -- Work with websockets
- ``RequestMiddleware``       -- Parse a scope and insert the parsed request into the scope
- ``ResponseMiddleware``      -- Parse responses and convert them into ASGI messages
- ``RouterMiddleware``        -- Route HTTP requests
- ``LifespanMiddleware``      -- Process a lifespan cycle
- ``StaticFilesMiddleware``   -- Serve static files from URL prefixes
- ``asgi_tools.tests.TestClient`` -- A test client with websockets support to test asgi applications
- ``App``                     -- A simple foundation for ASGI apps

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.6

.. _installation:

Installation
=============

**asgi-tools** should be installed using pip: ::

    pip install asgi-tools


Usage
=====

`asgi_tools.Request`, `asgi_tools.Response`
--------------------------------------------

Parse HTTP Request data from a scope and return it as JSON response:

.. code-block:: python

    import json
    from asgi_tools import Request, Response

    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return

        # Parse scope
        request = Request(scope, receive, send)
        request_data = {

            # Get full URL
            "url": str(request.url),

            "charset": request.charset,

            # Get headers
            "headers": {**request.headers},

            # Get query params
            "query": dict(request.query),

            # Get cookies
            "cookies": dict(request.cookies),

        }

        # Create a response (ResponseHTML, ResponseText, ResponseJSON, ResponseStream, ResponseFile, ResponseRedirect also available)
        response = Response(json.dumps(request_data), content_type="application/json")

        # Send ASGI messages
        return await response(scope, receive, send)


Response/Request Middlewares
-----------------------------

Automatically convert a scope into a ``asgi_tools.Request``

.. code-block:: python

    from asgi_tools import RequestMiddleware, ResponseHTML

    async def app(request, receive, send):
        # We will get a parsed request here
        data = await request.json()
        response = ResponseHTML(data['name'])
        return await response(request, receive, send)

    app = RequestMiddleware(app)


Automatically parse an result from asgi apps and convert it into a ``asgi_tools.Response``

.. code-block:: python

    from asgi_tools import ResponseMiddleware

    async def app(request, receive, send):
        return "Hello World!"

    app = ResponseMiddleware(app)


Router Middleware
------------------

Route HTTP requests

.. code-block:: python

    from http_router import Router
    from asgi_tools import RouterMiddleware, RequestMiddleware, ResponseMiddleware

    router = Router()

    @router.route('/page1')
    async def page1(request, receive, send):
        return 'page1'

    @router.route('/page2')
    async def page2(request, receive, send):
        return 'page2'

    # TODO


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

.. _Asyncio: https://docs.python.org/3/library/asyncio.html
.. _Trio: https://trio.readthedocs.io/en/stable/index.html
.. _klen: https://github.com/klen
.. _MIT license: http://opensource.org/licenses/MIT

