"""Simple Base for ASGI Apps."""

from functools import partial

from http_router import Router, NotFound

from .middleware import LifespanMiddleware
from .request import Request
from .response import parse_response, Response
from .utils import to_coroutine


class App:
    """ASGI Application.

    * Supports lifespan events.
    * Supports simple middlewares.
    * Supports routing.

    """

    exception_handlers = {}
    exception_handlers[NotFound] = to_coroutine(lambda exc: (404, 'Resource not Found'))
    exception_handlers[Exception] = to_coroutine(lambda exc: (500, 'Server Error'))

    def __init__(self, **kwargs):
        """Initialize router and lifespan middleware."""
        self.app = self.__process__
        self.router = Router(**kwargs)
        self.lifespan = LifespanMiddleware()
        self.lifespan.bind(self.app)

    async def __call__(self, scope, receive, send):
        """Process ASGI call."""
        request = Request(scope)
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
            for etype in type(exc).mro():
                handler = self.exception_handlers[etype]
                if handler:
                    break
            else:
                raise

            response = await handler(exc)

        return await parse_response(response)

    def route(self, *args, **kwargs):
        """Register an route."""
        def wrapper(cb):
            return self.router.route(*args, **kwargs)(to_coroutine(cb))
        return wrapper

    def middleware(self, md):
        """Register an simple middleware."""
        self.app = partial(to_coroutine(md), self.app)
        self.lifespan.bind(self.app)

    def on_startup(self, fn):
        """Register a startup handler."""
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn):
        """Register a shutdown handler."""
        return self.lifespan.on_shutdown(fn)

    def on_exception(self, etype):
        """Register an exception handler."""
        def wrapper(handler):
            self.exception_handlers[etype] = to_coroutine(handler)
        return wrapper