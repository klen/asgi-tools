"""Simple Base for ASGI Apps."""

from __future__ import annotations

from functools import partial
from inspect import isclass
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from http_router import PrefixedRoute

from asgi_tools.router import Router

from .errors import ASGIConnectionClosedError, ASGIInvalidMethodError, ASGINotFoundError
from .logs import logger
from .middleware import LifespanMiddleware, StaticFilesMiddleware, parse_response
from .request import Request
from .response import Response, ResponseError
from .utils import iscoroutinefunction, to_awaitable

if TYPE_CHECKING:
    import logging
    from pathlib import Path

    from http_router.types import TMethods, TPath

    from .types import (
        TASGIReceive,
        TASGIScope,
        TASGISend,
        TExceptionHandler,
        TVExceptionHandler,
    )

T = TypeVar("T")
TRouteHandler = TypeVar("TRouteHandler", bound=Callable[[Request], Any])
TCallable = TypeVar("TCallable", bound=Callable[..., Any])


class App:
    """A helper class to build ASGI applications quickly and efficiently.

    Features:
        - Routing with flexible path and method matching
        - ASGI-Tools :class:`Request`, :class:`Response` integration
        - Exception management and custom error handlers
        - Static files serving
        - Lifespan events (startup/shutdown)
        - Simple middleware support

    :param debug: Enable debug mode (more logging, raise unhandled exceptions)
    :type debug: bool
    :param logger: Custom logger for the application
    :type logger: logging.Logger
    :param static_url_prefix: URL prefix for static files
    :type static_url_prefix: str
    :param static_folders: List of folders to serve static files from
    :type static_folders: Optional[list[str | Path]]
    :param trim_last_slash: Treat "/path" and "/path/" as the same route
    :type trim_last_slash: bool
    :raises ValueError: If static_url_prefix is set without static_folders
    :raises TypeError: If static_folders is not a list of strings or Paths
    :raises RuntimeError: If the app is not an ASGI application

    Example:
        >>> from asgi_tools import App
        >>> app = App()
        >>> @app.route("/")
        ... async def homepage(request):
        ...     return "Hello, World!"
    """

    exception_handlers: dict[type[BaseException], TExceptionHandler]

    def __init__(
        self,
        *,
        debug: bool = False,
        logger: logging.Logger = logger,
        static_url_prefix: str = "/static",
        static_folders: list[str | Path] | None = None,
        trim_last_slash: bool = False,
    ):
        """Initialize the ASGI application with routing, logging, static files,
           and lifespan support.

        :param debug: Enable debug mode (more logging, raise unhandled exceptions)
        :type debug: bool
        :param logger: Custom logger for the application
        :type logger: logging.Logger
        :param static_url_prefix: URL prefix for static files
        :type static_url_prefix: str
        :param static_folders: List of folders to serve static files from
        :type static_folders: Optional[list[str|Path]]
        :param trim_last_slash: Treat "/path" and "/path/" as the same route
        :type trim_last_slash: bool
        """

        # Register base exception handlers
        self.exception_handlers = {
            ASGIConnectionClosedError: to_awaitable(lambda _, __: None),
        }

        # Setup routing
        self.router = Router(
            trim_last_slash=trim_last_slash, validator=callable, converter=to_awaitable
        )

        # Setup logging
        self.logger = logger

        # Setup app
        self.__app__ = self.__match__

        # Setup lifespan
        self.lifespan = LifespanMiddleware(
            self.__process__, ignore_errors=not debug, logger=self.logger
        )

        # Enable middleware for static files
        if static_folders and static_url_prefix:
            md = StaticFilesMiddleware.setup(folders=static_folders, url_prefix=static_url_prefix)
            self.middleware(md)

        # Debug mode
        self.debug = debug

        # Handle unknown exceptions
        if not debug:

            async def handle_unknown_exception(_: Request, exc: BaseException) -> Response:
                self.logger.exception(exc)
                return ResponseError.INTERNAL_SERVER_ERROR()

            self.exception_handlers[Exception] = handle_unknown_exception

        self.internal_middlewares: list = []

    async def __call__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend) -> None:
        """ASGI entrypoint. Converts the given scope into a request and processes it."""
        await self.lifespan(scope, receive, send)

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Internal request processing: builds a Request, calls the app, and handles exceptions."""
        scope["app"] = self
        request = Request(scope, receive, send)
        try:
            response: Response | None = await self.__app__(request, receive, send)
            if response is not None:
                await response(scope, receive, send)

        # Handle exceptions
        except BaseException as exc:
            for etype in type(exc).mro():
                if etype in self.exception_handlers:
                    await parse_response(
                        await self.exception_handlers[etype](request, exc),
                    )(scope, receive, send)
                    break
            else:
                if isinstance(exc, Response):
                    await exc(scope, receive, send)
                else:
                    raise

    async def __match__(
        self, request: Request, _: TASGIReceive, send: TASGISend
    ) -> Response | None:
        """Finds and calls a route handler, parses the response, and handles routing exceptions."""
        scope = request.scope
        path = f"{ scope.get('root_path', '') }{ scope['path'] }"
        try:
            match = self.router(path, scope.get("method", "GET"))

        except ASGINotFoundError as exc:
            raise ResponseError.NOT_FOUND() from exc

        except ASGIInvalidMethodError as exc:
            raise ResponseError.METHOD_NOT_ALLOWED() from exc

        scope["endpoint"] = match.target
        scope["path_params"] = {} if match.params is None else match.params
        handler = cast("Callable[[Request], Any]", match.target)
        response = await handler(request)

        if scope["type"] == "http":
            return parse_response(response)

        # TODO: Do we need to close websockets automatically?
        # if scope_type == "websocket" send websocket.close

        return None

    def __route__(self, router: Router, *prefixes: str, **_) -> "App":
        """Mount this app as a nested application under given prefixes."""
        for prefix in prefixes:
            route = RouteApp(prefix, set(), target=self)
            router.dynamic.insert(0, route)
        return self

    def middleware(self, md: TCallable, *, insert_first: bool = False) -> TCallable:
        """Register a middleware for the application.

        Middleware can be a coroutine (request/response) or a regular callable (lifespan).

        :param md: The middleware function or class
        :type md: TCallable
        :param insert_first: If True, insert as the first middleware
        :type insert_first: bool
        :return: The registered middleware
        :rtype: TCallable

        Example:
            >>> @app.middleware
            ... async def log_requests(handler, request):
            ...     print(f"Request: {request.method} {request.url}")
            ...     return await handler(request)
        """
        # Register as a simple middleware
        if iscoroutinefunction(md):
            if md not in self.internal_middlewares:
                if insert_first:
                    self.internal_middlewares.insert(0, md)
                else:
                    self.internal_middlewares.append(md)

            app = self.__match__
            for md_ in reversed(self.internal_middlewares):
                app = partial(md_, app)

            self.__app__ = app

        else:
            self.lifespan.bind(md(self.lifespan.app))

        return md

    def route(
        self, *paths: TPath, methods: TMethods | None = None, **opts: Any
    ) -> Callable[[TRouteHandler], TRouteHandler]:
        """Register a route handler.

        :param paths: One or more URL paths to match
        :type paths: TPath
        :param methods: HTTP methods to match (GET, POST, etc.)
        :type methods: Optional[TMethods]
        :param opts: Additional options for the route
        :type opts: Any
        :return: Decorator function
        :rtype: Callable[[TRouteHandler], TRouteHandler]
        """
        return self.router.route(*paths, methods=methods, **opts)

    def on_startup(self, fn: Callable) -> None:
        """Register a startup event handler.

        :param fn: The function to call on startup
        :type fn: Callable
        """
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn: Callable) -> None:
        """Register a shutdown event handler.

        :param fn: The function to call on shutdown
        :type fn: Callable
        """
        return self.lifespan.on_shutdown(fn)

    def on_error(self, etype: type[BaseException]):
        """Register a custom exception handler for a given exception type.

        :param etype: The exception type to handle
        :type etype: type[BaseException]
        :return: A decorator to register the handler
        :rtype: Callable

        Example:
            >>> @app.on_error(TimeoutError)
            ... async def timeout_handler(request, error):
            ...     return 'Timeout occurred'
        """
        assert isclass(etype), f"Invalid exception type: {etype}"
        assert issubclass(etype, BaseException), f"Invalid exception type: {etype}"

        def recorder(handler: TVExceptionHandler) -> TVExceptionHandler:
            self.exception_handlers[etype] = to_awaitable(handler)
            return handler

        return recorder


class RouteApp(PrefixedRoute):
    """Custom route to submount an application under a given path prefix."""

    def __init__(self, path: str, methods: set, target: App):
        """Create a submounted app callable for the given prefix."""
        path = path.rstrip("/")

        def app(request: Request):
            subrequest = request.__copy__(path=request.path[len(path) :])
            return target.__app__(subrequest, request.receive, request.send)

        super().__init__(path, methods, app)
