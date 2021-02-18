"""Simple Base for ASGI Apps."""

import inspect
import logging
import typing as t
from functools import partial

from http_router import Router as HTTPRouter
from http_router._types import TYPE_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed, ASGIConnectionClosed, asgi_logger
from ._types import Scope, Receive, Send, F
from .middleware import (
    BaseMiddeware,
    LifespanMiddleware,
    ResponseMiddleware,
    StaticFilesMiddleware,
    parse_response
)
from .request import Request
from .response import ResponseError, Response
from .utils import to_awaitable, iscoroutinefunction, is_awaitable


HTTP_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH'}


class Router(HTTPRouter):
    """Rebind router errors."""

    NotFound: t.ClassVar[t.Type[Exception]] = ASGINotFound
    RouterError: t.ClassVar[t.Type[Exception]] = ASGIError
    MethodNotAllowed: t.ClassVar[t.Type[Exception]] = ASGIMethodNotAllowed


class HTTPView:
    """Class Based Views."""

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


class AppResponseMiddleware(ResponseMiddleware):
    """Convert app results into a response but not send ASGI messages."""

    scopes = {'http'}

    __call__ = ResponseMiddleware.__process__


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
        self.__internal__ = AppInternalMiddleware(self.__process__)  # type: ignore

        # Register base exception handlers
        self.exception_handlers = {
            ASGIConnectionClosed: to_awaitable(lambda exc: None),
            Exception: to_awaitable(lambda exc: ResponseError.INTERNAL_SERVER_ERROR()),
        }

        # Setup routing
        self.router = Router(trim_last_slash=trim_last_slash, validator=is_awaitable)

        # Setup logging
        self.logger = logger

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

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Convert the given scope into a request and process."""
        request = Request(scope, receive, send)
        request['app'] = self
        try:
            await self.lifespan(request, receive, send)

        # Handle exceptions
        except BaseException as exc:
            response = await self.handle_exc(exc)
            if response is ...:
                raise

            await parse_response(response)(scope, receive, send)

    async def __process__(
            self, request: Request, receive: Receive, send: Send) -> t.Optional[Response]:
        """Find and call a callback, parse a response, handle exceptions."""
        try:
            path = f"{ request.get('root_path', '') }{ request['path'] }"
            match = self.router(path, request.get('method', 'GET'))
            request['path_params'] = {} if match.path_params is None else match.path_params
            response = await match.target(request)  # type: ignore
            if response is None and request['type'] == 'websocket':
                return None

            return parse_response(response)

        except ASGINotFound:
            raise ResponseError.NOT_FOUND()

        except ASGIMethodNotAllowed:
            raise ResponseError.METHOD_NOT_ALLOWED()

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
