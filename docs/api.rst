API Reference
=============

.. module:: asgi_tools

This part of the documentation covers all the interfaces of ASGI-Tools.

Request
-------

.. autoclass:: Request

    The class gives you an nicer interface to incoming HTTP request.

    .. code-block:: python

        from asgi_tools import Request, Response

        async def app(scope, receive, send):
            request = Request(scope, receive)
            content = f"{ request.method } { request.url.path }"
            response = Response(content)
            await response(scope, receive, send)

    Requests are based on a given scope and represents a mapping interface.

    .. code-block:: python

        request = Request(scope)
        assert request['version'] == scope['version']
        assert request['method'] == scope['method']
        assert request['scheme'] == scope['scheme']
        assert request['path'] == scope['path']

        # and etc

        # ASGI Scope keys also are available as Request attrubutes.

        assert request.version == scope['version']
        assert request.method == scope['method']
        assert request.scheme == scope['scheme']

    .. autoattribute:: headers

    .. autoattribute:: cookies

    .. autoattribute:: query

    .. autoattribute:: charset

    .. autoattribute:: content_type

    .. autoattribute:: url

    .. automethod:: stream

        .. code-block:: python

            from asgi_tools import Request, Response

            async def app(scope, receive, send):
                request = Request(scope, receive)
                body = b''
                async for chunk in request.stream():
                    body += chunk

                response = Response(body, content_type=request.content_type)
                await response(scope, receive, send)

    .. automethod:: body

    .. automethod:: text

    .. automethod:: form

    .. automethod:: json

    .. automethod:: data

Responses
---------

.. autoclass:: Response

    A helper to make http responses.

    .. code-block:: python

        from asgi_tools import Response

        async def app(scope, receive, send):
            response = Response('Hello, world!', content_type='text/plain')
            await response(scope, receive, send)

    .. autoattribute:: headers

    .. autoattribute:: cookies

        .. code-block:: python

            from asgi_tools import Response

            async def app(scope, receive, send):
                response = Response('OK')
                response.cookies["rocky"] = "road"
                response.cookies["rocky"]["path"] = "/cookie"
                await response(scope, receive, send)

    .. automethod:: __call__


ResponseText
^^^^^^^^^^^^

.. autoclass:: ResponseText

    .. code-block:: python

        from asgi_tools import ResponseText

        async def app(scope, receive, send):
            response = ResponseText('Hello, world!')
            await response(scope, receive, send)


ResponseHTML
^^^^^^^^^^^^

.. autoclass:: ResponseHTML

    .. code-block:: python

        from asgi_tools import ResponseHTML

        async def app(scope, receive, send):
            response = ResponseHTML('<h1>Hello, world!</h1>')
            await response(scope, receive, send)


ResponseJSON
^^^^^^^^^^^^

.. autoclass:: ResponseJSON

    .. code-block:: python

        from asgi_tools import ResponseJSON

        async def app(scope, receive, send):
            response = ResponseJSON({'hello': 'world'})
            await response(scope, receive, send)

ResponseRedirect
^^^^^^^^^^^^^^^^

.. autoclass:: ResponseRedirect

    .. code-block:: python

        from asgi_tools import ResponseRedirect

        async def app(scope, receive, send):
            response = ResponseRedirect('/login')
            await response(scope, receive, send)

    If you are using :py:class:`asgi_tools.App` or :py:class:`asgi_tools.ResponseMiddleware` you
    are able to raise the :py:class:`ResponseRedirect` as an exception.

    .. code-block:: python

        from asgi_tools import ResponseRedirect, Request, ResponseMiddleware

        async def app(scope, receive, send):
            request = Request(scope, receive)
            if not request.headers.get('authorization):
                raise ResponseRedirect('/login')

            return 'OK'

        app = ResponseMiddleware(app)

ResponseError
^^^^^^^^^^^^^

.. py:class:: ResponseError(message=None, status_code=500, **kwargs)

    A helper to return HTTP errors. Uses a 500 status code by default.

    .. :comment: ***

    :param message: A string with the error's message (HTTPStatus messages will be used by default)

    .. code-block:: python

        from asgi_tools import ResponseError

        async def app(scope, receive, send):
            response = ResponseError('Timeout', 502)
            await response(scope, receive, send)

    If you are using :py:class:`asgi_tools.App` or :py:class:`asgi_tools.ResponseMiddleware` you
    are able to raise the :py:class:`ResponseError` as an exception.

    .. code-block:: python

        from asgi_tools import ResponseError, Request, ResponseMiddleware

        async def app(scope, receive, send):
            request = Request(scope, receive)
            if not request.method == 'POST':
                raise ResponseError('Invalid request data', 400)

            return 'OK'

        app = ResponseMiddleware(app)

    You able to use :py:class:`http.HTTPStatus` properties with the `ResponseError` class

    .. code-block:: python

        response = ResponseError.BAD_REQUEST('invalid data')
        response = ResponseError.NOT_FOUND()
        response = ResponseError.BAD_GATEWAY()
        # and etc

ResponseStream
^^^^^^^^^^^^^^

.. autoclass:: ResponseStream

    .. code-block:: python

        from asgi_tools import ResponseStream
        from asgi_tools.utils import aio_sleep  # for compatability with different async libs

        async def stream_response():
            for number in range(10):
                await aio_sleep(1)
                yield str(number)

        async def app(scope, receive, send):
            generator = stream_response()
            response = ResponseStream(generator, content_type='plain/text')
            await response(scope, receive, send)

ResponseSSE
^^^^^^^^^^^

.. autoclass:: ResponseSSE

    .. code-block:: python

        from asgi_tools import ResponseSSE
        from asgi_tools.utils import aio_sleep  # for compatability with different async libs

        async def stream_response():
            for number in range(10):
                await aio_sleep(1)
                # The response support messages as text
                yield "data: message text"

                # And as dictionaties as weel
                yield {
                    "event": "ping",
                    "data": time.time(),
                }

        async def app(scope, receive, send):
            generator = stream_response()
            response = ResponseSSE(generator)
            await response(scope, receive, send)


ResponseFile
^^^^^^^^^^^^

.. autoclass:: ResponseFile

    .. code-block:: python

        from asgi_tools import ResponseFile

        async def app(scope, receive, send):

            # Return file
            if scope['path'] == '/selfie':
                response = ResponseFile('/storage/my_best_selfie.jpeg')

            # Download file
            else:
                response = ResponseFile('/storage/video-2020-01-01.mp4', filename='movie.mp4')

            await response(scope, receive, send)

ResponseWebSocket
^^^^^^^^^^^^^^^^^

.. autoclass:: ResponseWebSocket

    .. code-block:: python

        from asgi_tools import ResponseWebsocket

        async def app(scope, receive, send):
            async with ResponseWebSocket(scope, receive, send) as ws:
                msg = await ws.receive()
                assert msg == 'ping'
                await ws.send('pong')

    .. automethod:: accept

    .. automethod:: close

    .. automethod:: send

    .. automethod:: send_json

    .. automethod:: receive

Middlewares
-----------

RequestMiddleware
^^^^^^^^^^^^^^^^^^

.. autoclass:: RequestMiddleware


ResponseMiddleware
^^^^^^^^^^^^^^^^^^

.. autoclass:: ResponseMiddleware


LifespanMiddleware
^^^^^^^^^^^^^^^^^^

.. autoclass:: LifespanMiddleware
   :members: on_startup, on_shutdown


RouterMiddleware
^^^^^^^^^^^^^^^^

.. autoclass:: RouterMiddleware


StaticFilesMiddleware
^^^^^^^^^^^^^^^^^^^^^

.. autoclass:: StaticFilesMiddleware

Application
-----------

.. autoclass:: App

   .. automethod:: route

   .. automethod:: on_startup

   .. automethod:: on_shutdown

   .. automethod:: on_error

   .. automethod:: middleware

        The :meth:`App.middleware` supports two types of middlewares, see below:

        .. code-block:: python

            from asgi_tools import App, Request, ResponseError

            app = App()

            # Register a "classic" middleware, you able to use any ASGI middleware
            @app.middleware
            def classic_middleware(app):
                async def handler(scope, receive, send):
                    if not Request(scope).headers['authorization']:
                        response = ResponseError.UNAUTHORIZED()
                        await response(scope, receive, send)
                    else:
                        await app(scope, receive, send)

                return handler

            # You also are able to register the middleware as: `app.middleware(classic_middleware)`

            # Register a "simplier" middleware
            # The middlewares is guaranted to get a response from app and should return a response
            # also
            @app.middleware
            async def simple_middleware(app, request, receive, send):
                response = await app(request, receive, send)
                response.headers['x-agent'] = 'SimpleX'
                return response

        .. admonition:: Middleware Exceptions

            Any exception raised from an middleware wouldn't be catched by the app

Class Based Views
-----------------

.. autoclass:: HTTPView


TestClient
-----------

.. autoclass:: asgi_tools.tests.ASGITestClient

   .. automethod:: request

        .. code-block:: python

            from asgi_tools import App
            from asgi_tools.tests import ASGITestClient

            app = Application()

            @app.route('/')
            async def index(request):
                return 'OK'

            async def test_app():
                client = ASGITestClient(app)
                response = await client.get('/')
                assert response.status_code == 200
                assert await response.text() == 'OK'

        Stream Request

        .. code-block:: python

            async def test_app():
                client = ASGITestClient(app)
                async def stream():
                    for n in range(10):
                        yield b'chunk%s' % bytes(n)
                        await aio_sleep(1)

                response = await client.get('/', data=stream)
                assert response.status_code == 200


        Stream Response

        .. code-block:: python

            @app.route('/')
            async def index(request):
                async def stream():
                    for n in range(10):
                        yield b'chunk%s' % bytes(n)
                        await aio_sleep(1)

                return ResponseStream(stream)


            async def test_app():
                client = ASGITestClient(app)
                response = await client.get('/')
                assert response.status_code == 200
                async for chunk in response.stream():
                    assert chunk.startswith('chunk')


   .. automethod:: websocket

        .. code-block:: python

            from asgi_tools import App, ResponseWebSocket
            from asgi_tools.tests import ASGITestClient

            app = Application()

            @app.route('/websocket')
            async def websocket(request):
                async with ResponseWebSocket(request) as ws:
                    msg = await ws.receive()
                    assert msg == 'ping'
                    await ws.send('pong')

            async def test_app():
                client = ASGITestClient(app)
                await ws.send('ping')
                msg = await ws.receive()
                assert msg == 'pong'

   .. automethod:: lifespan

        .. code-block:: python

            from asgi_tools import ResponseHTML
            from asgi_tools.tests import ASGITestClient

            SIDE_EFFECTS = {'started': False, 'finished': False}

            async def app(scope, receive, send):
                # Process lifespan events
                if scope['type'] == 'lifespan':
                    while True:
                        msg = await receive()
                        if msg['type'] == 'lifespan.startup':
                            SIDE_EFFECTS['started'] = True
                            await send({'type': 'lifespan.startup.complete'})

                        elif msg['type'] == 'lifespan.shutdown':
                            SIDE_EFFECTS['finished'] = True
                            await send({'type': 'lifespan.shutdown.complete'})
                            return

                # Otherwise return HTML response
                await ResponseHTML('OK')(scope, receive, send)

            client = Client(app)

            async with client.lifespan():
                assert SIDE_EFFECTS['started']
                assert not SIDE_EFFECTS['finished']
                res = await client.get('/')
                assert res.status_code == 200

            assert SIDE_EFFECTS['started']
            assert SIDE_EFFECTS['finished']

.. Links

.. _ASGI: https://asgi.readthedocs.io/en/latest/
