"""ASGI-Tools Middlewares."""

from http_router import Router

from .request import Request
from .response import HTMLResponse, parse_response
from .utils import to_coroutine


class BaseMiddeware:
    """Base class for ASGI-Tools middlewares."""

    scopes = {'http', 'websockets'}

    def __init__(self, app=None, **kwargs):
        """Save ASGI App."""

        self.app = app or HTMLResponse("Not Found", status_code=404)

    async def __call__(self, scope, *args, **kwargs):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.process(scope, *args, **kwargs)

        return await self.app(scope, *args, **kwargs)

    def __getattr__(self, name):
        """Proxy middleware methods to root level."""

        return getattr(self.app, name)

    async def process(self, scope, receive, send):
        """Do the middleware's logic."""

        raise NotImplementedError()


class RequestMiddleware(BaseMiddeware):
    """Provider asgi_tools.Request to apps."""

    def __init__(self, app=None, pass_request=False, **kwargs):
        """Initialize the middleware.

        :param pass_request: pass a request instead a scope to ASGI Application
        """
        super(RequestMiddleware, self).__init__(app, **kwargs)
        self.pass_request = pass_request

    async def process(self, scope, *args, **kwargs):
        """Parse the scope into a request and integrate it into the scope."""

        request = Request(scope, *args)
        if self.pass_request:
            return await self.app(request, **kwargs)

        scope['request'] = request
        return await self.app(scope, *args, **kwargs)


class ResponseMiddleware(BaseMiddeware):
    """Support asgi_tools.Response."""

    async def process(self, *args, **kwargs):
        """Parse responses from callbacks."""

        res = await self.app(*args, **kwargs)
        if res:
            res = await parse_response(res)
            await res(*args, **kwargs)


class LifespanMiddleware(BaseMiddeware):
    """Manage lifespan events."""

    scopes = {'lifespan'}

    def __init__(self, app=None, on_startup=None, on_shutdown=None, **kwargs):
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

    def __init__(
            self, app=None, routes=None, raise_not_found=True,
            trim_last_slash=False, pass_params=False, **kwargs):
        """Initialize HTTP router."""
        super(RouterMiddleware, self).__init__(app, **kwargs)
        self.router = Router(raise_not_found=raise_not_found, trim_last_slash=trim_last_slash)
        self.pass_params = pass_params
        if routes:
            for path, cb in routes.items():
                self.router.route(path)(cb)

    async def process(self, scope, *args, **kwargs):
        """Get an app and process."""
        app, params = self.dispatch(scope)
        if self.pass_params:
            return await app(scope, *args, **params)
        scope['router'] = params
        return await app(scope, *args, **kwargs)

    def dispatch(self, scope):
        """Lookup for a callback."""
        try:
            return self.router(scope.get("root_path", "") + scope["path"], scope['method'])
        except self.router.NotFound:
            return self.app, {}

    def route(self, *args, **kwargs):
        """Register an route."""
        return self.router.route(*args, **kwargs)


def AppMiddleware(app=None, **params):
    """Combine middlewares to create an application."""

    async def default404(request, *args, **kwargs):
        return HTMLResponse("Not Found", status_code=404)

    return combine(
        app or default404,
        LifespanMiddleware, ResponseMiddleware, RequestMiddleware, RouterMiddleware,
        pass_params=True, pass_request=True, **params)


def combine(app, *middlewares, **params):
    """Combine the given middlewares into the given application."""

    for md in list(middlewares)[::-1]:
        app = md(app, **params)

    return app
