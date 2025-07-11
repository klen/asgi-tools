Usage
=====

ASGI Applications with ASGI-Tools
---------------------------------

**ASGI-Tools** is designed as a flexible ASGI_ toolkit. You can use any of its components independently, or leverage the high-level :class:`asgi_tools.App` to build applications quickly.

.. note::
   For low-level API details, see the :doc:`api` documentation.

Quick Start Example
~~~~~~~~~~~~~~~~~~~

Here's a minimal ASGI application:

.. code-block:: python

    from asgi_tools import App

    app = App()

    @app.route("/")
    async def hello_world(request):
        return "<p>Hello, World!</p>"

Save it as :file:`hello.py` or something similar.
Run it with an ASGI server:

.. code-block:: sh

    uvicorn hello:app

Visit http://127.0.0.1:8000/ to see your application running.

Request Object
--------------

Route handlers receive a **Request** object providing convenient access to the ASGI scope and request data.

Commonly Used Properties
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    @app.route('/example')
    async def example(request):
        method = request.method
        path = request.url.path
        query = request.query
        headers = request.headers
        cookies = request.cookies
        content_type = request.content_type
        charset = request.charset

        return f"Method: {method}, Path: {path}"

Form Data and File Uploads
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    @app.route('/upload', methods=['POST'])
    async def upload(request):
        form = await request.form()
        username = form.get('username')

        if 'file' in form:
            file = form['file']
            content = await file.read()
            # Process file...

        return "Upload successful"

JSON Data
~~~~~~~~~

.. code-block:: python

    @app.route('/api/data', methods=['POST'])
    async def handle_json(request):
        data = await request.json()
        name = data.get('name')
        value = data.get('value')
        return {"status": "success"}

Cookies
~~~~~~~

Access cookies as a dictionary:

.. code-block:: python

    session = request.cookies.get('session', '')

Routing
-------

ASGI-Tools provides a powerful routing system via :meth:`~asgi_tools.App.route`.

Basic Routing
~~~~~~~~~~~~~

.. code-block:: python

    @app.route('/')
    async def index(request):
        return 'Index Page'

    @app.route('/hello', '/hello/world')
    async def hello(request):
        return 'Hello, World!'

    @app.route('/only-post', methods=['POST'])
    async def only_post(request):
        return request.method

Dynamic URLs
~~~~~~~~~~~~

Support dynamic URL parameters:

.. code-block:: python

    @app.route('/user/{username}')
    async def show_user_profile(request):
        username = request.path_params['username']
        return f'User {username}'

URL Converters
~~~~~~~~~~~~~~

Specify variable types:

========= ====================================
``str``   (default) accepts any text without a slash
``int``   accepts positive integers
``float`` accepts positive floating point values
``path``  like string but accepts slashes
``uuid``  accepts UUID strings
========= ====================================

Example:

.. code-block:: python

    @app.route('/post/{post_id:int}')
    async def show_post(request):
        post_id = request.path_params['post_id']
        return f'Post #{post_id}'

Custom Regex Patterns
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    import re

    @app.route(re.compile(r'/orders/(a|b|c)/?'))
    async def orders(request):
        return request.path

Static Files
------------

Serve static files by configuring folders on app initialization:

.. code-block:: python

    app = App(
        static_url_prefix='/static',
        static_folders=['static', 'public']
    )

Access via:

* ``/static/css/style.css``
* ``/static/js/app.js``
* ``/static/images/logo.png``

Middleware
----------

ASGI-Tools provides essential middleware:

RequestMiddleware
~~~~~~~~~~~~~~~~~

.. code-block:: python

    from asgi_tools import RequestMiddleware

    app = RequestMiddleware(app)

ResponseMiddleware
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from asgi_tools import ResponseMiddleware

    app = ResponseMiddleware(app)

LifespanMiddleware
~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from asgi_tools import LifespanMiddleware

    app = LifespanMiddleware(app)

    @app.on_startup
    async def startup():
        # Initialize resources
        pass

    @app.on_shutdown
    async def shutdown():
        # Cleanup resources
        pass

Error Handling
--------------

Register custom error handlers:

.. code-block:: python

    from asgi_tools.response import ResponseError

    @app.on_error(TimeoutError)
    async def handle_timeout(request, error):
        return 'Request timeout', 504

    @app.on_error(ResponseError)
    async def handle_http_error(request, error):
        if error.status_code == 404:
            return 'Not Found', 404
        return error

Testing
-------

Use the built-in test client:

.. code-block:: python

    from asgi_tools.tests import ASGITestClient

    client = ASGITestClient(app)

    response = await client.get('/')
    assert response.status_code == 200
    assert await response.text() == 'Hello, World!'

    response = await client.post('/login', data={'username': 'test', 'password': 'secret'})
    assert response.status_code == 200

WebSocket Testing
~~~~~~~~~~~~~~~~~

.. code-block:: python

    async with client.websocket('/ws') as ws:
        await ws.send('Hello')
        msg = await ws.receive()
        assert msg == 'Hello, Client!'

.. _ASGI: https://asgi.readthedocs.io/en/latest/
