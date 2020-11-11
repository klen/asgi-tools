"""ASGI-Tools Middlewares."""

from asyncio import iscoroutine

from http_router import Router

from . import SUPPORTED_SCOPES
from .request import Request
from .response import Response, PlainTextResponse, HTMLResponse, JSONResponse
from .utils import to_coroutine


async def parse_response(response):
    """Parse the given object and convert it into a asgi_tools.Response."""

    while iscoroutine(response):
        response = await response

    if isinstance(response, Response):
        return response

    if isinstance(response, (str, bytes)):
        return HTMLResponse(response)

    if isinstance(response, tuple):
        status, *response = response
        response = await parse_response(*(response or ['']))
        response.status_code = status
        return response

    if isinstance(response, (dict, list, int, bool)):
        return JSONResponse(response)

    return PlainTextResponse(str(response))


class BaseMiddeware:
    """Base class for ASGI-Tools middlewares."""

    scopes = {'http', 'websockets'}

    def __init__(self, app, **kwargs):
        """Save ASGI App."""

        self.app = app

    async def __call__(self, scope, receive, send):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.process(scope, receive, send)

        return await self.app(scope, receive, send)

    async def process(self, scope, receive, send):
        """Do the middleware's logic."""

        raise NotImplementedError()


class RequestMiddleware(BaseMiddeware):
    """Provider asgi_tools.Request to apps."""

    async def process(self, scope, receive, send):
        """Parse the scope into a request and integrate it into the scope."""

        scope['request'] = Request(scope, receive, send)
        return await self.app(scope, receive, send)


class ResponseMiddleware(BaseMiddeware):
    """Support asgi_tools.Response."""

    async def process(self, scope, receive, send):
        """Parse responses from callbacks."""

        res = await self.app(scope, receive, send)
        if res:
            res = await parse_response(res)
            await res(scope, receive, send)


class LifespanMiddleware(BaseMiddeware):
    """Manage lifespan events."""

    scopes = {'lifespan'}

    def __init__(self, app, on_startup=None, on_shutdown=None, **kwargs):
        """Prepare the middleware."""
        super(LifespanMiddleware, self).__init__(app, **kwargs)
        self._startup = []
        self._shutdown = []
        self.register(on_startup, self._startup)
        self.register(on_shutdown, self._shutdown)

    async def process(self, scope, receive, send):
        """Manage lifespan cycle."""
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await self.startup(scope)
                await send({'type': 'lifespan.startup.complete'})

            elif message['type'] == 'lifespan.shutdown':
                await self.shutdown(scope)
                return await send({'type': 'lifespan.shutdown.complete'})

    def register(self, handlers, container):
        """Register lifespan handlers."""
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += [to_coroutine(fn) for fn in handlers]
        return container

    def on_startup(self, fn):
        """Add a function to startup."""
        self.register(fn, self._startup)

    def on_shutdown(self, fn):
        """Add a function to shutdown."""
        self.register(fn, self._shutdown)

    async def startup(self, scope):
        """Run startup callbacks."""
        for fn in self._startup:
            await fn()

    async def shutdown(self, scope):
        """Run shutdown callbacks."""
        for fn in self._shutdown:
            await fn()


class RouterMiddleware(BaseMiddeware):
    """Bind callbacks to HTTP paths."""

    def __init__(self, app, routes=None, **kwargs):
        """Initialize HTTP router."""
        super(RouterMiddleware, self).__init__(app, **kwargs)
        self.router = Router(**kwargs)
        if routes:
            for path, cb in routes.items():
                self.router.route(path)(cb)

    async def process(self, scope, receive, send):
        """Get an app and process."""
        app, opts = self.dispatch(scope)
        scope['router'] = opts
        return await app(scope, receive, send)

    def dispatch(self, scope):
        """Lookup for a callback."""
        try:
            return self.router(scope.get("root_path", "") + scope["path"], scope['method'])
        except self.router.NotFound:
            return self.app, {}

    def route(self, *args, **kwargs):
        """Register an route."""
        return self.router.route(*args, **kwargs)


class AppMiddleware(LifespanMiddleware, RouterMiddleware):
    """Combine all middlewares into one."""

    def __init__(self, app=None, **kwargs):
        """Prepare the middleware."""
        if not app:
            async def app(request, **kwargs):
                return Response('Not Found', status_code=404)

        super(AppMiddleware, self).__init__(app, **kwargs)

    async def __call__(self, scope, receive, send):
        """Parse requests, responses, route queries."""
        if scope['type'] not in SUPPORTED_SCOPES:
            return await super().__call__(scope, receive, send)

        request = Request(scope, receive, send)
        app, opts = self.dispatch(scope)
        response = await app(request, **opts)
        app = await parse_response(response)
        await app(scope, receive, send)


def combine(app, *middlewares):
    """Combine the given middlewares into an application."""

    for md in list(middlewares)[::-1]:
        app = md(app)

    return app
