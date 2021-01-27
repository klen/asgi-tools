"""Simple Base for ASGI Apps."""

import inspect
import logging
import typing as t
from functools import partial

from http_router import Router, TYPE_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed, ASGIConnectionClosed
from ._types import Scope, Receive, Send
from .middleware import LifespanMiddleware, StaticFilesMiddleware, ASGIApp
from .request import Request
from .response import parse_response, Response, ResponseError
from .utils import to_awaitable, iscoroutinefunction, is_awaitable


HTTP_METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH'}


class HTTPView:
    """Class Based Views."""

    def __new__(cls, request: Request, **path_params):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **path_params)

    @classmethod
    def __route__(cls, router: Router, *paths: str,
                  methods: TYPE_METHODS = None, **params) -> t.Type['HTTPView']:
        """Bind the class view to the given router."""
        view_methods = dict(inspect.getmembers(cls, inspect.isfunction))
        methods = methods or [m for m in HTTP_METHODS if m.lower() in view_methods]
        return router.bind(cls, *paths, methods=methods, **params)

    def __call__(self, request: Request, **path_params) -> t.Awaitable:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, request.method.lower())
        return method(request, **path_params)


class App:
    """ASGI Application.

    * Supports lifespan events.
    * Supports simple middlewares.
    * Supports routing.

    """

    exception_handlers: t.Dict[t.Type[BaseException], t.Callable[[BaseException], t.Optional[Response]]] = {}  # noqa
    exception_handlers[Exception] = to_awaitable(lambda exc: ResponseError(500))
    exception_handlers[ASGINotFound] = to_awaitable(lambda exc: ResponseError(404))
    exception_handlers[ASGIMethodNotAllowed] = to_awaitable(lambda exc: ResponseError(405))
    exception_handlers[ASGIConnectionClosed] = to_awaitable(lambda exc: None)

    def __init__(self, *, debug: bool = False, logger: logging.Logger = None,
                 static_folders: t.Union[str, t.List[str]] = None,
                 static_url_prefix: str = '/static', trim_last_slash: bool = False):
        """Initialize router and lifespan middleware."""
        self.app: ASGIApp = self.__process__  # type: ignore

        # Setup routing
        self.router = Router(trim_last_slash=trim_last_slash, validate_cb=is_awaitable)
        self.router.NotFound = ASGINotFound
        self.router.MethodNotAllowed = ASGIMethodNotAllowed
        self.route = self.router.route

        # Setup logging
        self.logger = logger or logging.getLogger('asgi-tools')

        # Setup static files
        if static_folders and static_url_prefix:
            self.app = StaticFilesMiddleware(
                self.app, folders=static_folders, url_prefix=static_url_prefix)

        # Setup lifespan
        self.lifespan = LifespanMiddleware(self.app)

        # Setup excetions
        self.exception_handlers = dict(self.exception_handlers)

        # Debug mode
        self.debug = debug
        if self.debug:
            self.logger.setLevel('DEBUG')
            del self.exception_handlers[Exception]

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Process ASGI call."""
        scope = Request(scope, receive, send)
        scope['app'] = self

        try:
            response = await self.lifespan(scope, receive, send)

        except BaseException as exc:
            handler = self.__process_exception(exc)
            if handler:
                response = await handler(exc)
                response = await parse_response(response)

            elif isinstance(exc, Response):
                response = exc

            else:
                raise

        if isinstance(response, Response):
            await response(scope, receive, send)

    async def __process__(
            self, scope: Request, receive: Receive, send: Send) -> t.Optional[Response]:
        """Find and call a callback, process a response."""
        match = self.router(scope.url.path, scope.get('method') or 'GET')
        scope['path_params'] = match.path_params
        response = await match.callback(scope)
        if response is None and scope['type'] == 'websocket':
            return None

        return await parse_response(response)

    def __process_exception(self, exc: BaseException) -> t.Union[t.Callable, None]:
        for etype in type(exc).mro():
            handler = self.exception_handlers.get(etype)
            if handler:
                return handler

        return None

    def middleware(self, md: t.Callable):
        """Register an middleware to internal cycle."""
        # Register as a simple middleware
        self.app = iscoroutinefunction(md) and partial(md, self.app) or md(self.app)
        self.lifespan.bind(self.app)

    def on_startup(self, fn: t.Callable):
        """Register a startup handler."""
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn: t.Callable):
        """Register a shutdown handler."""
        return self.lifespan.on_shutdown(fn)

    def on_exception(self, etype: t.Type[BaseException]) -> t.Callable:
        """Register an exception handler."""
        if not (inspect.isclass(etype) and issubclass(etype, BaseException)):
            raise ASGIError('Wrong argument: %s' % etype)

        def wrapper(handler):
            self.exception_handlers[etype] = to_awaitable(handler)
        return wrapper
