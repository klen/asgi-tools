"""Simple Base for ASGI Apps."""

import logging
from functools import partial
import inspect

from http_router import Router, METHODS as HTTP_METHODS

from . import ASGIError, ASGINotFound, ASGIMethodNotAllowed
from .middleware import LifespanMiddleware, StaticFilesMiddleware
from .request import Request
from .response import parse_response, Response, ResponseError
from .utils import to_awaitable, iscoroutinefunction


class HTTPView:
    """Class Based Views."""

    def __new__(cls, request=None, **matches):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **matches)

    @classmethod
    def __route__(cls, router, *paths, **params):
        """Bind the class view to the given router."""
        methods = dict(inspect.getmembers(cls, inspect.isfunction))
        params.setdefault('methods', [m for m in HTTP_METHODS if m.lower() in methods])
        return router.route(*paths, **params)(cls)

    def __call__(self, request, **matches):
        """Dispatch the given request by HTTP method."""
        method = getattr(
            self, request.method.lower(), App.exception_handlers[ASGIMethodNotAllowed])
        return method(request, **matches)


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

    async def __call__(self, scope, receive, send):
        """Process ASGI call."""
        request = Request(scope, receive, send)
        request.app = scope['app'] = self
        response = await self.lifespan(request, receive, send)
        if isinstance(response, Response):
            await response(scope, receive, send)

    async def __process__(self, request, receive, send):
        """Find and call a callback."""
        try:
            cb, matches = self.router(request.url.path, request.method)
            response = await cb(request, **matches)

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

        return await parse_response(response)

    def route(self, *args, **kwargs):
        """Register an route."""
        def wrapper(cb):
            if hasattr(cb, '__route__'):
                return cb.__route__(self.router, *args, **kwargs)
            return self.router.route(*args, **kwargs)(to_awaitable(cb))
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
