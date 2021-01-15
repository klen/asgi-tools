"""Simple Base for ASGI Apps."""

import logging
from functools import partial
import inspect

from http_router import Router, METHODS as HTTP_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed, ASGIConnectionClosed
from .middleware import LifespanMiddleware, StaticFilesMiddleware
from .request import Request
from .response import parse_response, Response, ResponseError
from .utils import to_awaitable, iscoroutinefunction, is_awaitable


class HTTPView:
    """Class Based Views."""

    def __new__(cls, request=None, **path_params):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **path_params)

    @classmethod
    def __route__(cls, router, *paths, **params):
        """Bind the class view to the given router."""
        methods = dict(inspect.getmembers(cls, inspect.isfunction))
        params.setdefault('methods', [m for m in HTTP_METHODS if m.lower() in methods])
        return router.route(*paths, **params)(cls)

    def __call__(self, request, **path_params):
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

    exception_handlers = {}
    exception_handlers[Exception] = to_awaitable(lambda exc: ResponseError(500))
    exception_handlers[ASGINotFound] = to_awaitable(lambda exc: ResponseError(404))
    exception_handlers[ASGIMethodNotAllowed] = to_awaitable(lambda exc: ResponseError(405))
    exception_handlers[ASGIConnectionClosed] = to_awaitable(lambda exc: None)

    def __init__(self, logger=None, static_folders=None, static_url_prefix='/static', **kwargs):
        """Initialize router and lifespan middleware."""
        self.app = self.__process__

        self.router = Router(**kwargs)
        self.router.NotFound = ASGINotFound
        self.router.MethodNotAllowed = ASGIMethodNotAllowed

        self.logger = logger or logging.getLogger('asgi-tools')
        if static_folders and static_url_prefix:
            self.app = StaticFilesMiddleware(
                self.app, folders=static_folders, url_prefix=static_url_prefix)

        self.lifespan = LifespanMiddleware()
        self.lifespan.bind(self.app)

        self.exception_handlers = dict(self.exception_handlers)

    async def __call__(self, scope, receive, send):
        """Process ASGI call."""
        scope['app'] = self
        scope = Request(scope, receive, send)
        response = await self.lifespan(scope, receive, send)
        if isinstance(response, Response):
            await response(scope, receive, send)

    async def __process__(self, scope, receive, send):
        """Find and call a callback."""
        try:
            cb, scope['path_params'] = self.router(scope.url.path, scope.get('method'))
            response = await cb(scope)

        # Process exceptions
        except Exception as exc:
            if isinstance(exc, ResponseError) and ResponseError not in self.exception_handlers:
                return exc

            for etype in type(exc).mro():
                handler = self.exception_handlers.get(etype)
                if handler:
                    break

            else:
                raise

            response = await handler(exc)

        if response is None and scope['type'] == 'websocket':
            return

        return await parse_response(response)

    def route(self, *args, **kwargs):
        """Register an route."""
        def wrapper(cb):
            if hasattr(cb, '__route__'):
                return cb.__route__(self.router, *args, **kwargs)

            if not is_awaitable(cb):
                raise TypeError('Cannot use `app.route` once a callback is not awaitable.')

            return self.router.route(*args, **kwargs)(cb)

        return wrapper

    def middleware(self, md):
        """Register an middleware to internal cycle."""
        # Register as a simple middleware
        self.app = iscoroutinefunction(md) and partial(md, self.app) or md(self.app)
        self.lifespan.bind(self.app)

    def on_startup(self, fn):
        """Register a startup handler."""
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn):
        """Register a shutdown handler."""
        return self.lifespan.on_shutdown(fn)

    def on_exception(self, etype):
        """Register an exception handler."""
        if not (inspect.isclass(etype) and issubclass(etype, Exception)):
            raise ASGIError('Wrong argument: %s' % etype)

        def wrapper(handler):
            self.exception_handlers[etype] = to_awaitable(handler)
        return wrapper
