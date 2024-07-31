"""Simple Base for ASGI Apps."""

from __future__ import annotations

from functools import partial
from inspect import isclass
from typing import TYPE_CHECKING, Callable, Optional, Union  # py39

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
        TVCallable,
        TVExceptionHandler,
    )


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

    exception_handlers: dict[type[BaseException], TExceptionHandler]

    def __init__(
        self,
        *,
        debug: bool = False,
        logger: logging.Logger = logger,
        static_url_prefix: str = "/static",
        static_folders: Optional[list[Union[str, Path]]] = None,
        trim_last_slash: bool = False,
    ):
        """Initialize router and lifespan middleware."""

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
        """Convert the given scope into a request and process."""
        await self.lifespan(scope, receive, send)

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Send ASGI messages."""
        scope["app"] = self
        request = Request(scope, receive, send)
        try:
            response: Optional[Response] = await self.__app__(request, receive, send)
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
    ) -> Optional[Response]:
        """Find and call a callback, parse a response, handle exceptions."""
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
        response = await match.target(request)  # type: ignore[]

        if scope["type"] == "http":
            return parse_response(response)

        # TODO: Do we need to close websockets automatically?
        # if scope_type == "websocket" send websocket.close

        return None

    def __route__(self, router: Router, *prefixes: str, **_) -> "App":
        """Mount self as a nested application."""
        for prefix in prefixes:
            route = RouteApp(prefix, set(), target=self)
            router.dynamic.insert(0, route)
        return self

    def middleware(self, md: TVCallable, *, insert_first: bool = False) -> TVCallable:
        """Register a middleware."""
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

    def route(self, *paths: TPath, methods: Optional[TMethods] = None, **opts):
        """Register a route."""
        return self.router.route(*paths, methods=methods, **opts)

    def on_startup(self, fn: Callable) -> None:
        """Register a startup handler."""
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn: Callable) -> None:
        """Register a shutdown handler."""
        return self.lifespan.on_shutdown(fn)

    def on_error(self, etype: type[BaseException]):
        """Register an exception handler.

        .. code-block::

            @app.on_error(TimeoutError)
            async def timeout(request, error):
                return 'Something bad happens'

            @app.on_error(ResponseError)
            async def process_http_errors(request, response_error):
                if response_error.status_code == 404:
                    return render_template('page_not_found.html'), 404
                return response_error

        """
        assert isclass(etype), f"Invalid exception type: {etype}"
        assert issubclass(etype, BaseException), f"Invalid exception type: {etype}"

        def recorder(handler: TVExceptionHandler) -> TVExceptionHandler:
            self.exception_handlers[etype] = to_awaitable(handler)
            return handler

        return recorder


class RouteApp(PrefixedRoute):
    """Custom route to submount an application."""

    def __init__(self, path: str, methods: set, target: App):
        """Create app callable."""
        path = path.rstrip("/")

        def app(request: Request):
            subrequest = request.__copy__(path=request.path[len(path) :])
            return target.__app__(subrequest, request.receive, request.send)

        super().__init__(path, methods, app)
