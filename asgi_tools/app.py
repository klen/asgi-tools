"""Simple Base for ASGI Apps."""

import typing as t
import logging
from functools import partial
import inspect

from http_router import Router, METHODS as HTTP_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed, ASGIConnectionClosed
from .middleware import LifespanMiddleware, StaticFilesMiddleware, ASGIApp
from .request import Request
from .response import parse_response, Response, ResponseError
from .utils import to_awaitable, iscoroutinefunction, is_awaitable
from .types import Scope, Receive, Send


class HTTPView:
    """Class Based Views."""

    def __new__(cls, request: Request, **path_params):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **path_params)

    @classmethod
    def __route__(cls, router: Router, *paths: str, **params) -> t.Callable:
        """Bind the class view to the given router."""
        methods = dict(inspect.getmembers(cls, inspect.isfunction))
        params.setdefault('methods', [m for m in HTTP_METHODS if m.lower() in methods])
        return router.route(*paths, **params)(cls)

    def __call__(self, request: Request, **path_params) -> t.Awaitable:
        """Dispatch the given request by HTTP method."""
        method = getattr(
            self, request.method.lower(), App.exception_handlers[ASGIMethodNotAllowed])
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

        self.router = Router(trim_last_slash=trim_last_slash)
        self.router.NotFound = ASGINotFound
        self.router.MethodNotAllowed = ASGIMethodNotAllowed

        self.logger = logger or logging.getLogger('asgi-tools')

        if static_folders and static_url_prefix:
            self.app = StaticFilesMiddleware(
                self.app, folders=static_folders, url_prefix=static_url_prefix)

        self.lifespan = LifespanMiddleware(self.app)

        self.exception_handlers = dict(self.exception_handlers)

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
        cb, scope['path_params'] = self.router(scope.url.path, scope.get('method') or 'GET')
        response = await cb(scope)
        if response is None and scope['type'] == 'websocket':
            return None

        response = await parse_response(response)
        return response

    def __process_exception(self, exc: BaseException) -> t.Union[t.Callable, None]:
        for etype in type(exc).mro():
            handler = self.exception_handlers.get(etype)
            if handler:
                return handler

        return None

    def route(self, *args, **kwargs):
        """Register an route."""
        def wrapper(cb):
            if hasattr(cb, '__route__'):
                return cb.__route__(self.router, *args, **kwargs)

            if not is_awaitable(cb):
                raise TypeError('Cannot use `app.route` once a callback is not awaitable.')

            return self.router.route(*args, **kwargs)(cb)

        return wrapper

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
