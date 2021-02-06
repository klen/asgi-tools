API
===

.. module:: asgi_tools

This part of the documentation covers all the interfaces of ASGI-Tools.

Request
-------

.. autoclass:: Request
    :members: method, url, headers, cookies, charset, content_type, stream, body, text, form, data

Responses
---------

.. autoclass:: Response
    :members: __call__, headers, cookies

ResponseText
^^^^^^^^^^^^

.. autoclass:: ResponseText

ResponseHTML
^^^^^^^^^^^^

.. autoclass:: ResponseHTML

ResponseJSON
^^^^^^^^^^^^

.. autoclass:: ResponseJSON

ResponseRedirect
^^^^^^^^^^^^^^^^

.. autoclass:: ResponseRedirect

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

ResponseFile
^^^^^^^^^^^^

.. autoclass:: ResponseFile

ResponseWebSocket
^^^^^^^^^^^^^^^^^

.. autoclass:: ResponseWebSocket


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
