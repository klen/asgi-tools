ASGI-Tools
##########

.. _description:

**asgi-tools** -- Tools to make ASGI Applications

**Features:**

- `Request`             -- Parse ASGI scope, get url, headers, cookies, read a request's data/json/form-data
- `Response`            -- Send HTTP (html, json) responses
- `RequestMiddleware`   -- Parse a scope and insert the parsed request into the scope
- `ResponseMiddleware`  -- Parse responses and convert them into ASGI messages
- `RouterMiddleware`    -- Route HTTP requests
- `LifespanMiddleware`  -- Process a lifespan cycle
- `AppMiddleware`       -- A combined (request, response, router, lifespan) middleware to quikly create ASGI apps

.. _badges:

.. image:: https://github.com/klen/asgi-tools/workflows/tests/badge.svg
    :target: https://github.com/klen/asgi-tools/actions
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: PYPI Version

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. _installation:

Installation
=============

**asgi-tools** should be installed using pip: ::

    pip install asgi-tools


Usage
=====

`asgi_tools.Request`, `asgi_tools.Response`
--------------------------------------------

Parse HTTP Request data from a scope and build a http response:

.. code-block:: python

   from asgi_tools import Request, Response


   template = "... any template for the HTML content here ..."


   async def app(scope, receive, send):
    if scope['type'] != 'http':
        return

    # Parse the given scope
    request = Request(scope, receive, send)
    # Render the page
    body = template.render(

        # Get full URL
        url=request.url,

        charset=request.charset,

        # Get headers
        headers=request.headers,

        # Get query params
        query=request.query,

        # Get cookies
        cookies=request.cookies,

        # Get a decoded request body (the methods: request.body, request.form, request.json also available)
        text=await request.text(),

    )

    # Render a response as HTML (HTMLResponse, PlainTextResponse, JSONResponse, StreamResponse, RedirectResponse also available)
    return await Response(body, content_type="text/html")(scope, receive, send)


Response/Request Middlewares
-----------------------------

Automatically convert a scope into a `asgi_tools.Request`

.. code-block:: python

    from asgi_tools import RequestMiddleware


    async def base_app(request, receive, send):
        assert request.url
        assert request.headers
        # ...

    app = RequestMiddleware(base_app)


Automatically parse an result from asgi apps and convert it into a `asgi_tools.Response`

.. code-block:: python

    from asgi_tools import ResponseMiddleware


    async def base_app(request, receive, send):
        return "Hello World!"

    app = ResponseMiddleware(base_app)


Router Middleware
------------------

Route HTTP requests

.. code-block:: python

    from asgi_tools import RouterMiddleware, ResponseMiddleware


    async def index_and_default(*args):
        return "Hello from Index"


    async def page1(*args):
        return "Hello from Page1"


    async def page2(*args):
        return "Hello from Page2"


    app = ResponseMiddleware(RouterMiddleware(index_and_default, routes={'/page1': page1, '/page2': page2}))


Alternative usage

.. code-block:: python

    from asgi_tools import RouterMiddleware, ResponseMiddleware


    async def index_and_default(*args):
        return "Hello from Index"


    router = RouterMiddleware(index_and_default)


    @router.route('/page1')
    async def page1(*args):
        return "Hello from Page1"


    @router.route('/page2')
    async def page2(*args):
        return "Hello from Page2"


    app = ResponseMiddleware(router)


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

.. _klen: https://github.com/klen
.. _MIT license: http://opensource.org/licenses/MIT

