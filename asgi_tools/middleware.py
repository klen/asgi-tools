"""ASGI-Tools Middlewares."""

from functools import wraps

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

    def bind(self, app):
        """Bind the middleware to an ASGI application."""
        self.app = app

    async def __call__(self, scope, *args, **kwargs):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.process(scope, *args, **kwargs)

        return await self.app(scope, *args, **kwargs)

    def __getattr__(self, name):
        """Proxy middleware methods to root level."""

        return getattr(self.app, name)

    @classmethod
    def setup(cls, **params):
        """Curry the middleware, prepare it to use."""

        @wraps(cls)
        def closure(*args, **kwargs):
            params.update(kwargs)
            return cls(*args, **params)

        return closure

    async def process(self, scope, receive, send):
        """Do the middleware's logic."""

        raise NotImplementedError()


class ResponseMiddleware(BaseMiddeware):
    """Parse different responses from ASGI applications."""

    def __init__(self, app=None, parse_response_only=False, **kwargs):
        """Setup the middleware."""
        super(ResponseMiddleware, self).__init__(app=app, **kwargs)
        self.parse_response_only = parse_response_only

    async def process(self, scope, receive, send):
        """Parse responses from callbacks."""

        response = await self.app(scope, receive, send)
        if response:
            response = await parse_response(response)
            if self.parse_response_only:
                return response

            # Process the response
            async for msg in response:
                await send(msg)


class RequestMiddleware(BaseMiddeware):
    """Provider asgi_tools.Request to apps."""

    async def process(self, scope, receive, send):
        """Replace scope with request object."""
        return await self.app(Request(scope, receive, send), receive, send)


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
            self, app=None, routes=None, middlewares=None,
            raise_not_found=True, trim_last_slash=False, pass_params_only=False, **kwargs):
        """Initialize HTTP router."""
        super(RouterMiddleware, self).__init__(app, **kwargs)
        self.router = Router(raise_not_found=raise_not_found, trim_last_slash=trim_last_slash)
        self.pass_params_only = pass_params_only
        if routes:
            for path, cb in routes.items():
                self.router.route(path)(cb)

    async def process(self, scope, receive, send):
        """Get an app and process."""
        app, params = self.dispatch(scope)
        if self.pass_params_only:
            return await app(scope, **params)
        scope['router'] = params
        return await app(scope, receive, send)

    def dispatch(self, scope):
        """Lookup for a callback."""
        try:
            return self.router(scope.get("root_path", "") + scope["path"], scope['method'])
        except self.router.NotFound:
            return self.app, {}

    def route(self, *args, **kwargs):
        """Register an route. Integrate middlewares."""
        return self.router.route(*args, **kwargs)


def AppMiddleware(app=None, *app_middlewares, pass_params_only=True, **params):
    """Combine middlewares to create an application."""

    async def default404(request, **params):
        return HTMLResponse("Not Found", status_code=404)

    middlewares = [LifespanMiddleware, RequestMiddleware, ResponseMiddleware]
    if app_middlewares:
        middlewares = [
            *middlewares, *app_middlewares, ResponseMiddleware.setup(parse_response_only=True)
        ]

    middlewares.append(RouterMiddleware.setup(pass_params_only=pass_params_only))
    return combine(app or default404, *middlewares, **params)


def combine(app, *middlewares, **params):
    """Combine the given middlewares into the given application."""

    for md in list(middlewares)[::-1]:
        app = md(app, **params)

    return app
