"""Simple Base for ASGI Apps."""

import inspect
import logging
import typing as t
from functools import partial

from http_router import Router as HTTPRouter, PrefixedRoute
from http_router.typing import TYPE_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed, ASGIConnectionClosed, asgi_logger
from .middleware import (
    BaseMiddeware,
    LifespanMiddleware,
    StaticFilesMiddleware,
    parse_response
)
from .request import Request
from .response import ResponseError, Response
from .utils import to_awaitable, iscoroutinefunction
from .typing import Scope, Receive, Send, F


HTTP_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH'}


class Router(HTTPRouter):
    """Rebind router errors."""

    NotFound: t.ClassVar[t.Type[Exception]] = ASGINotFound
    RouterError: t.ClassVar[t.Type[Exception]] = ASGIError
    MethodNotAllowed: t.ClassVar[t.Type[Exception]] = ASGIMethodNotAllowed


class HTTPView:
    """Class-based view pattern for handling HTTP method dispatching.

    .. code-block:: python

        @app.route('/custom')
        class CustomEndpoint(HTTPView):

            async def get(self, request):
                return 'Hello from GET'

            async def post(self, request):
                return 'Hello from POST'

        # ...
        async def test_my_endpoint(client):
            response = await client.get('/custom')
            assert await response.text() == 'Hello from GET'

            response = await client.post('/custom')
            assert await response.text() == 'Hello from POST'

            response = await client.put('/custom')
            assert response.status_code == 405

    """

    def __new__(cls, request: Request, *args, **opts):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **opts)

    @classmethod
    def __route__(cls, router: Router, *paths: str,
                  methods: TYPE_METHODS = None, **params) -> t.Type['HTTPView']:
        """Bind the class view to the given router."""
        view_methods = dict(inspect.getmembers(cls, inspect.isfunction))
        methods = methods or [m for m in HTTP_METHODS if m.lower() in view_methods]
        return router.bind(cls, *paths, methods=methods, **params)

    def __call__(self, request: Request, *args, **opts) -> t.Awaitable:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, request.method.lower())
        return method(request, **opts)


class AppInternalMiddleware(BaseMiddeware):
    """Process responses."""

    scopes = {'http'}

    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Send ASGI messages."""
        response = await self.app(scope, receive, send)
        await response(scope, receive, send)


class App:
    """A helper to build ASGI Applications.

    Features:

    * Routing
    * ASGI-Tools :class:`Request`, :class:`Response`
    * Exception management
    * Static files
    * Lifespan events
    * Simplest middlewares

    :param debug: Enable debug mode (more logging, raise unhandled exceptions)
    :type debug: bool, False

    :param logger: Custom logger for the application
    :type logger: logging.Logger

    :param static_url_prefix: A prefix for static files
    :type static_url_prefix: str, "/static"

    :param static_folders: A list of folders to look static files
    :type static_folders: list[str]

    :param trim_last_slash: Consider "/path" and "/path/" as the same
    :type trim_last_slash: bool, False

    """

    exception_handlers: t.Dict[
        t.Union[int, t.Type[BaseException]],
        t.Callable[[BaseException], t.Awaitable]
    ]

    def __init__(self, *, debug: bool = False,
                 logger: logging.Logger = asgi_logger,
                 static_url_prefix: str = '/static',
                 static_folders: t.Union[str, t.List[str]] = None, trim_last_slash: bool = False):
        """Initialize router and lifespan middleware."""

        # Register base exception handlers
        self.exception_handlers = {
            ASGIConnectionClosed: to_awaitable(lambda exc: None),
            Exception: to_awaitable(lambda exc: ResponseError.INTERNAL_SERVER_ERROR()),
        }

        # Setup routing
        self.router = router = Router(
            trim_last_slash=trim_last_slash, validator=callable, converter=to_awaitable)

        # Setup logging
        self.logger = logger

        async def process(request: Request, receive: Receive, send: Send) -> t.Optional[Response]:
            """Find and call a callback, parse a response, handle exceptions."""
            scope = request.scope
            path = f"{ scope.get('root_path', '') }{ scope['path'] }"
            try:
                match = router(path, scope.get('method', 'GET'))
            except ASGINotFound:
                raise ResponseError.NOT_FOUND()
            except ASGIMethodNotAllowed:
                raise ResponseError.METHOD_NOT_ALLOWED()

            scope['path_params'] = {} if match.params is None else match.params
            response = await match.target(request)  # type: ignore
            if response is None and request['type'] == 'websocket':
                return None

            return parse_response(response)

        self.__internal__ = AppInternalMiddleware(process)  # type: ignore

        # Setup lifespan
        self.lifespan = LifespanMiddleware(
            self.__internal__, ignore_errors=not debug, logger=self.logger)

        # Enable middleware for static files
        if static_folders and static_url_prefix:
            md = StaticFilesMiddleware.setup(folders=static_folders, url_prefix=static_url_prefix)
            self.middleware(md)

        # Debug mode
        self.debug = debug
        if self.debug:
            self.logger.setLevel('DEBUG')
            del self.exception_handlers[Exception]

    def __route__(self, router: Router, *prefixes: str, methods: TYPE_METHODS = None, **params):
        """Mount self as a nested application."""
        def target(request):
            return self.__internal__(request, request.receive, request.send)

        for prefix in prefixes:
            route = RouteApp(prefix, set(), target=self)
            router.dynamic.insert(0, route)
        return self

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Convert the given scope into a request and process."""
        scope['app'] = self
        try:
            await self.lifespan(Request(scope, receive, send), receive, send)
        except BaseException as exc:  # Handle exceptions
            response = await self.handle_exc(exc)
            if response is ...:
                raise

            await parse_response(response)(scope, receive, send)

    async def handle_exc(self, exc: BaseException) -> t.Any:
        """Look for a handler for the given exception."""
        if isinstance(exc, Response) and exc.status_code in self.exception_handlers:
            return await self.exception_handlers[exc.status_code](exc)

        for etype in type(exc).mro():
            if etype in self.exception_handlers:
                return await self.exception_handlers[etype](exc)

        return exc if isinstance(exc, Response) else ...

    def middleware(self, md: F) -> F:
        """Register a middleware."""
        # Register as a simple middleware
        if iscoroutinefunction(md):
            self.__internal__.bind(partial(md, self.__internal__.app))
        else:
            self.lifespan.bind(md(self.lifespan.app))

        return md

    def route(self, *args, **kwargs) -> t.Callable:
        """Register a route."""
        return self.router.route(*args, **kwargs)

    def on_startup(self, fn: t.Callable):
        """Register a startup handler."""
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn: t.Callable):
        """Register a shutdown handler."""
        return self.lifespan.on_shutdown(fn)

    def on_error(self, etype: t.Union[int, t.Type[BaseException]]):
        """Register an exception handler."""
        def recorder(handler: F) -> F:
            self.exception_handlers[etype] = to_awaitable(handler)
            return handler

        return recorder


class RouteApp(PrefixedRoute):
    """Custom route to submount an application."""

    def __init__(self, path: str, methods: t.Set, target: App):
        """Create app callable."""
        path = path.rstrip('/')

        def app(request: Request):
            subrequest = request.__copy__(path=request.path[len(path):])
            receive = t.cast(Receive, request.receive)
            send = t.cast(Send, request.send)
            return target.__internal__.app(subrequest, receive, send)

        super(RouteApp, self).__init__(path, methods, app)
