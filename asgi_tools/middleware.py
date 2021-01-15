"""ASGI-Tools Middlewares."""

from functools import partial
from pathlib import Path

from http_router import Router

from . import ASGIError
from .request import Request
from .response import ResponseHTML, parse_response, ResponseError, ResponseFile
from .utils import to_awaitable


#  TODO: StaticFilesMiddleware


class BaseMiddeware:
    """Base class for ASGI-Tools middlewares."""

    scopes = {'http', 'websocket'}

    def __init__(self, app=None, **params):
        """Save ASGI App."""

        self.bind(app)

    async def __call__(self, scope, *args, **kwargs):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.__process__(scope, *args, **kwargs)

        return await self.app(scope, *args, **kwargs)

    async def __process__(self, scope, receive, send):
        """Do the middleware's logic."""

        raise NotImplementedError()

    @classmethod
    def setup(cls, **params):
        """Setup the middleware without an initialization."""
        return partial(cls, **params)

    def bind(self, app=None):
        """Rebind the middleware to an ASGI application if it has been inited already."""
        self.app = app or ResponseHTML("Not Found", status_code=404)
        return self


class ResponseMiddleware(BaseMiddeware):
    """Parse different responses from ASGI applications."""

    async def __process__(self, scope, receive, send):
        """Parse responses from callbacks."""

        try:
            response = await self.app(scope, receive, send)
            if response is None:
                return

            response = await parse_response(response)

        except ResponseError as exc:
            response = exc

        # Send ASGI messages from the prepared response
        async for msg in response:
            await send(msg)


class RequestMiddleware(BaseMiddeware):
    """Provider asgi_tools.Request to apps."""

    async def __process__(self, scope, receive, send):
        """Replace scope with request object."""
        return await self.app(Request(scope, receive, send), receive, send)


class LifespanMiddleware(BaseMiddeware):
    """Manage lifespan events."""

    scopes = {'lifespan'}

    def __init__(self, app=None, on_startup=None, on_shutdown=None, **params):
        """Prepare the middleware."""
        super(LifespanMiddleware, self).__init__(app, **params)
        self._startup = []
        self._shutdown = []
        self.__register__(on_startup, self._startup)
        self.__register__(on_shutdown, self._shutdown)

    async def __process__(self, scope, receive, send):
        """Manage lifespan cycle."""
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await self.__startup__(scope)
                await send({'type': 'lifespan.startup.complete'})

            elif message['type'] == 'lifespan.shutdown':
                await self.__shutdown__(scope)
                return await send({'type': 'lifespan.shutdown.complete'})

    def __register__(self, handlers, container):
        """Register lifespan handlers."""
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += [to_awaitable(fn) for fn in handlers]
        return container

    async def __startup__(self, scope):
        """Run startup callbacks."""
        for fn in self._startup:
            await fn()

    async def __shutdown__(self, scope):
        """Run shutdown callbacks."""
        for fn in self._shutdown:
            await fn()

    def on_startup(self, fn):
        """Add a function to startup."""
        self.__register__(fn, self._startup)

    def on_shutdown(self, fn):
        """Add a function to shutdown."""
        self.__register__(fn, self._shutdown)


class RouterMiddleware(BaseMiddeware):
    """Bind callbacks to HTTP paths."""

    def __init__(self, app=None, router: Router = None, **params):
        """Initialize HTTP router. """
        super(RouterMiddleware, self).__init__(app, **params)
        self.router = router

    async def __process__(self, scope, receive, send):
        """Get an app and process."""
        app, path_params = self.__dispatch__(scope)
        scope['path_params'] = path_params
        return await app(scope, receive, send)

    def __dispatch__(self, scope):
        """Lookup for a callback."""
        try:
            return self.router(scope.get("root_path", "") + scope["path"], scope['method'])
        except self.router.NotFound:
            return self.app, {}


class StaticFilesMiddleware(BaseMiddeware):
    """Serve static files."""

    def __init__(self, app=None, url_prefix='/static', folders=None, **params) -> None:
        """Initialize the middleware. """
        super(StaticFilesMiddleware, self).__init__(app, **params)
        self.url_prefix = url_prefix
        folders = folders or []
        if isinstance(folders, str):
            folders = [folders]
        self.folders = [Path(folder) for folder in folders]

    async def __process__(self, scope, receive, send):
        """Serve static files for self url prefix."""
        if not self.folders or not scope['path'].startswith(self.url_prefix):
            return await self.app(scope, receive, send)

        filename = scope['path'][len(self.url_prefix):].strip('/')
        for folder in self.folders:
            filepath = folder.joinpath(filename).resolve()
            try:
                response = ResponseFile(filepath, headers_only=scope['method'] == 'HEAD')
                break

            except ASGIError:
                response = None

        response = response or ResponseError(404)

        async for msg in response:
            await send(msg)


def AppMiddleware(
        app=None, *app_middlewares, **params):
    """Combine middlewares to create an application."""

    async def default404(request, **params):
        return ResponseHTML("Not Found", status_code=404)

    middlewares = [
        LifespanMiddleware, RequestMiddleware, ResponseMiddleware,
        *app_middlewares, RouterMiddleware
    ]
    return combine(app or default404, *middlewares, **params)


def combine(app, *middlewares, **params):
    """Combine the given middlewares into the given application."""

    for md in list(middlewares)[::-1]:
        app = md(app, **params)

    return app
