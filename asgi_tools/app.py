"""Simple Base for ASGI Apps."""

import logging
from functools import partial

from http_router import Router, NotFound

from .middleware import LifespanMiddleware
from .request import Request
from .response import parse_response, Response, ResponseError
from .utils import to_coroutine, iscoroutinefunction


class App:
    """ASGI Application.

    * Supports lifespan events.
    * Supports simple middlewares.
    * Supports routing.

    """

    exception_handlers = {}
    exception_handlers[Exception] = to_coroutine(lambda exc: ResponseError(500))

    def __init__(self, logger=None, **kwargs):
        """Initialize router and lifespan middleware."""
        self.app = self.__process__
        self.router = Router(**kwargs)
        self.lifespan = LifespanMiddleware()
        self.lifespan.bind(self.app)
        self.logger = logger or logging.getLogger('asgi-tools')

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

        except ResponseError as exc:
            return exc

        except NotFound:
            return ResponseError(404)

        # Process exceptions
        except Exception as exc:
            self.logger.exception(exc)
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
            return self.router.route(*args, **kwargs)(to_coroutine(cb))
        return wrapper

    def middleware(self, md):
        """Register an middleware to internal cycle."""
        # Register as a simple middleware
        self.app = iscoroutinefunction(md) and partial(md, self.app) or to_coroutine(md(self.app))
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
