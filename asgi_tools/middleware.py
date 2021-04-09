"""ASGI-Tools Middlewares."""

import abc
import inspect
import typing as t
from functools import partial
from pathlib import Path

from http_router import Router

from . import ASGIError, asgi_logger
from ._types import Scope, Receive, Send, ASGIApp
from .request import Request
from .response import ResponseHTML, parse_response, ResponseError, ResponseFile, Response, ResponseRedirect


class BaseMiddeware(metaclass=abc.ABCMeta):
    """Base class for ASGI-Tools middlewares."""

    scopes: t.Union[t.Set, t.Sequence] = {'http', 'websocket'}

    def __init__(self, app: ASGIApp = None) -> None:
        """Save ASGI App."""

        self.bind(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.__process__(scope, receive, send)

        return await self.app(scope, receive, send)

    @abc.abstractmethod
    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Do the middleware's logic."""

        raise NotImplementedError()

    @classmethod
    def setup(cls, **params) -> t.Callable:
        """Setup the middleware without an initialization."""
        return partial(cls, **params)

    def bind(self, app: ASGIApp = None):
        """Rebind the middleware to an ASGI application if it has been inited already."""
        self.app = app or ResponseHTML("Not Found", status_code=404)
        return self


class ResponseMiddleware(BaseMiddeware):
    """Automatically convert ASGI_ apps results into responses :class:`~asgi_tools.Response` and
    send them to server as ASGI_ messages.

    .. code-block:: python

        from asgi_tools import ResponseMiddleware, ResponseText, ResponseRedirect

        async def app(scope, receive, send):
            # ResponseMiddleware catches ResponseError, ResponseRedirect and convert the exceptions
            # into HTTP response
            if scope['path'] == '/user':
                raise ResponseRedirect('/login')

            # Return ResponseHTML
            if scope['method'] == 'GET':
                return '<b>HTML is here</b>'

            # Return ResponseJSON
            if scope['method'] == 'POST':
                return {'json': 'here'}

            # Return any response explicitly
            if scope['method'] == 'PUT':
                return ResponseText('response is here')

            # Short form to responses: (status_code, body) or (status_code, body, headers)
            return 405, 'Unknown method'

        app = ResponseMiddleware(app)

    The conversion rules:

    * :class:`Response` objects will be directly returned from the view
    * ``dict``, ``list``, ``int``, ``bool``, ``None`` results will be converted into :class:`ResponseJSON`
    * ``str``, ``bytes`` results will be converted into :class:`ResponseHTML`
    * ``tuple[int, Any, dict]`` will be converted into a :class:`Response` with ``int`` status code, ``dict`` will be used as headers, ``Any`` will be used to define the response's type

    .. code-block:: python

        from asgi_tools import ResponseMiddleware

        # The result will be converted into HTML 404 response with the 'Not Found' body
        async def app(request, receive, send):
            return 404, 'Not Found'

        app = ResponseMiddleware(app)

    You are able to raise :class:`ResponseError` from yours ASGI_ apps and it will be catched and returned as a response

    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle ASGI call."""
        response = await self.__process__(scope, receive, send)
        if isinstance(response, Response):
            await response(scope, receive, send)

    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Parse responses from callbacks."""

        try:
            response = await self.app(scope, receive, send)
            if response is None and scope['type'] == 'websocket':
                return

            # Prepare a response
            return parse_response(response)

        except (ResponseError, ResponseRedirect) as exc:
            return exc


class RequestMiddleware(BaseMiddeware):
    """Automatically create :class:`asgi_tools.Request` from the scope and pass it to ASGI_ apps.

    .. code-block:: python

        from asgi_tools import RequestMiddleware, Response

        async def app(request, receive, send):
            content = f"{ request.method } { request.url.path }"
            response = Response(content)
            await response(scope, receive, send)

        app = RequestMiddleware(app)

    """

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Replace scope with request object."""
        return await self.app(Request(scope, receive, send), receive, send)


class LifespanMiddleware(BaseMiddeware):
    """Manage ASGI_ Lifespan events.

    :param ignore_errors: Ignore errors from startup/shutdown handlers
    :param on_startup: the list of callables to run when the app is starting
    :param on_shutdown: the list of callables to run when the app is finishing

    .. code-block:: python

        from asgi_tools import LifespanMiddleware, Response

        async def app(scope, receive, send):
            response = Response('OK')
            await response(scope, receive, send)

        app = lifespan = LifespanMiddleware(app)

        @lifespan.on_startup
        async def start():
            print('The app is starting')

        @lifespan.on_shutdown
        async def start():
            print('The app is finishing')

    Lifespan middleware may be used as an async context manager for testing purposes

    .. code-block: python

        async def test_my_app():

            # ...

            # Registered startup/shutdown handlers will be called
            async with lifespan:
                # ... do something

    """

    scopes = {'lifespan'}

    def __init__(self, app: ASGIApp = None, ignore_errors: bool = False, logger=asgi_logger,
                 on_startup: t.Union[t.Callable, t.List[t.Callable]] = None,
                 on_shutdown: t.Union[t.Callable, t.List[t.Callable]] = None) -> None:
        """Prepare the middleware."""
        super(LifespanMiddleware, self).__init__(app)
        self.ignore_errors = ignore_errors
        self.logger = logger
        self.__startup__: t.List[t.Callable] = []
        self.__shutdown__: t.List[t.Callable] = []
        self.__register__(on_startup, self.__startup__)
        self.__register__(on_shutdown, self.__shutdown__)

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Manage lifespan cycle."""
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                msg = await self.run('startup', send)
                await send(msg)

            elif message['type'] == 'lifespan.shutdown':
                msg = await self.run('shutdown', send)
                return await send(msg)

    def __register__(self, handlers: t.Union[t.Callable, t.List[t.Callable], None],
                     container: t.List[t.Callable]) -> None:
        """Register lifespan handlers."""
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += handlers

    async def __aenter__(self):
        """Use the lifespan middleware as a context manager."""
        await self.run('startup')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Use the lifespan middleware as a context manager."""
        await self.run('shutdown')

    async def run(self, event: str, send: Send = None):
        """Run startup/shutdown handlers."""
        assert event in {'startup', 'shutdown'}
        handlers = getattr(self, f"__{event}__")
        for handler in handlers:
            try:
                res = handler()
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:
                if self.ignore_errors:
                    continue

                self.logger.exception(exc)
                self.logger.error(
                    f"{ event.title() } method '{ handler }' raises an exception. "
                    "Lifespan process failed.")

                return {'type': f'lifespan.{event}.failed', 'message': str(exc)}

        return {'type': f'lifespan.{event}.complete'}

    def on_startup(self, fn: t.Callable) -> None:
        """Add a function to startup."""
        self.__register__(fn, self.__startup__)

    def on_shutdown(self, fn: t.Callable) -> None:
        """Add a function to shutdown."""
        self.__register__(fn, self.__shutdown__)


class RouterMiddleware(BaseMiddeware):
    r"""Manage routing.

    .. code-block:: python

        from asgi_tools import RouterMiddleware, ResponseHTML, ResponseError

        async def default_app(scope, receive, send):
            response = ResponseError.NOT_FOUND()
            await response(scope, receive, send)

        app = router = RouterMiddleware(default_app)

        @router.route('/status', '/stat')
        async def status(scope, receive, send):
            response = ResponseHTML('STATUS OK')
            await response(scope, receive, send)

        # Bind methods
        # ------------
        @router.route('/only-post', methods=['POST'])
        async def only_post(scope, receive, send):
            response = ResponseHTML('POST OK')
            await response(scope, receive, send)

        # Regexp paths
        # ------------
        import re

        @router.route(re.compile(r'/\d+/?'))
        async def num(scope, receive, send):
            num = int(scope['path'].strip('/'))
            response = ResponseHTML(f'Number { num }')
            await response(scope, receive, send)

        # Dynamic paths
        # -------------

        @router.route('/hello/{name}')
        async def hello(scope, receive, send):
            name = scope['path_params']['name']
            response = ResponseHTML(f'Hello { name.title() }')
            await response(scope, receive, send)

        # Set regexp for params
        @router.route(r'/multiply/{first:\d+}/{second:\d+}')
        async def multiply(scope, receive, send):
            first, second = map(int, scope['path_params'].values())
            response = ResponseHTML(str(first * second))
            await response(scope, receive, send)

    Path parameters are made available in the request/scope, as the ``path_params`` dictionary.

    """

    def __init__(self, app: ASGIApp = None, router: Router = None) -> None:
        """Initialize HTTP router. """
        super(RouterMiddleware, self).__init__(app)
        self.router = router or Router()

    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Get an app and process."""
        app, path_params = self.__dispatch__(scope)
        if not callable(app):
            app = self.app

        scope['path_params'] = path_params
        return await app(scope, receive, send)

    def __dispatch__(self, scope: Scope) -> t.Tuple[t.Optional[t.Any], t.Optional[t.Mapping]]:
        """Lookup for a callback."""
        try:
            match = self.router(scope.get("root_path", "") + scope["path"], scope['method'])
            return match.target, match.path_params

        except self.router.RouterError:
            return self.app, {}

    def route(self, *args, **kwargs):
        """Register a route."""
        return self.router.route(*args, **kwargs)


class StaticFilesMiddleware(BaseMiddeware):
    """Serve static files.

    :param url_prefix:  an URL prefix for static files
    :type url_prefix: str, "/static"
    :param folders: Paths to folders with static files
    :type folders: list[str]

    .. code-block:: python

        from asgi_tools import StaticFilesMiddleware, ResponseHTML

        async def app(scope, receive, send):
            response = ResponseHTML('OK)

        app = StaticFilesMiddleware(app, folders=['static'])

    """

    def __init__(self, app: ASGIApp = None, url_prefix: str = '/static',
                 folders: t.Union[str, t.List[str]] = None) -> None:
        """Initialize the middleware. """
        super(StaticFilesMiddleware, self).__init__(app)
        self.url_prefix = url_prefix
        folders = folders or []
        if isinstance(folders, str):
            folders = [folders]
        self.folders: t.List[Path] = [Path(folder) for folder in folders]

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve static files for self url prefix."""
        path = scope['path']
        if not path.startswith(self.url_prefix):
            return await self.app(scope, receive, send)

        filename = path[len(self.url_prefix):].strip('/')
        for folder in self.folders:
            filepath = folder.joinpath(filename).resolve()
            try:
                response: t.Optional[Response] = ResponseFile(
                    filepath, headers_only=scope['method'] == 'HEAD')
                break

            except ASGIError:
                response = None

        response = response or ResponseError(status_code=404)
        await response(scope, receive, send)

# pylama: ignore=E501
