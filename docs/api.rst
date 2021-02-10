API
===

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

    .. autoattribute:: method

    .. autoattribute:: url

    .. autoattribute:: headers

    .. autoattribute:: cookies

    .. autoattribute:: charset

    .. autoattribute:: content_type

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

ResponseFile
^^^^^^^^^^^^

.. autoclass:: ResponseFile

    .. code-block:: python

        from asgi_tools import ResponseFile

        async def app(scope, receive, send):
            response = ResponseFile('/storage/my_best_selfie.jpeg')
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
   :members: middleware, on_startup, on_shutdown, on_error, route

TestClient
-----------

.. autoclass:: asgi_tools.tests.ASGITestClient
   :members: request, websocket


.. Links

.. _ASGI: https://asgi.readthedocs.io/en/latest/
