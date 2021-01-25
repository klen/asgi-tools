"""ASGI-Tools Middlewares."""

import typing as t
from functools import partial
from pathlib import Path
import abc

from http_router import Router

from . import ASGIError
from .request import Request
from .response import ResponseHTML, parse_response, ResponseError, ResponseFile, Response
from .utils import to_awaitable
from .types import Scope, Receive, Send


ASGIApp = t.Callable[[t.Union[Scope, Request], Receive, Send], t.Awaitable]


class BaseMiddeware(metaclass=abc.ABCMeta):
    """Base class for ASGI-Tools middlewares."""

    scopes: t.Union[t.Set, t.Sequence] = {'http', 'websocket'}

    def __init__(self, app: ASGIApp = None) -> None:
        """Save ASGI App."""

        self.bind(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        """Handle ASGI call."""

        if scope['type'] in self.scopes:
            return await self.__process__(scope, receive, send)

        return await self.app(scope, receive, send)

    @abc.abstractmethod
    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Do the middleware's logic."""

        raise NotImplementedError()

    @classmethod
    def setup(cls, **params) -> t.Callable:
        """Setup the middleware without an initialization."""
        return partial(cls, **params)

    def bind(self, app: ASGIApp = None):
        """Rebind the middleware to an ASGI application if it has been inited already."""
        self.app = app or ResponseHTML("Not Found", status_code=404)
        return self


class ResponseMiddleware(BaseMiddeware):
    """Parse different responses from ASGI applications."""

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
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

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Replace scope with request object."""
        return await self.app(Request(scope, receive, send), receive, send)


class LifespanMiddleware(BaseMiddeware):
    """Manage lifespan events."""

    scopes = {'lifespan'}

    def __init__(self, app: ASGIApp = None,
                 on_startup: t.Union[t.Callable, t.List[t.Callable]] = None,
                 on_shutdown: t.Union[t.Callable, t.List[t.Callable]] = None) -> None:
        """Prepare the middleware."""
        super(LifespanMiddleware, self).__init__(app)
        self._startup: t.List[t.Callable] = []
        self._shutdown: t.List[t.Callable] = []
        self.__register__(on_startup, self._startup)
        self.__register__(on_shutdown, self._shutdown)

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Manage lifespan cycle."""
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await self.__startup__()
                await send({'type': 'lifespan.startup.complete'})

            elif message['type'] == 'lifespan.shutdown':
                await self.__shutdown__()
                return await send({'type': 'lifespan.shutdown.complete'})

    def __register__(self, handlers: t.Union[t.Callable, t.List[t.Callable], None],
                     container: t.List[t.Callable]) -> None:
        """Register lifespan handlers."""
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += [to_awaitable(fn) for fn in handlers]

    async def __startup__(self) -> None:
        """Run startup callbacks."""
        for fn in self._startup:
            await fn()

    async def __shutdown__(self) -> None:
        """Run shutdown callbacks."""
        for fn in self._shutdown:
            await fn()

    def on_startup(self, fn: t.Callable) -> None:
        """Add a function to startup."""
        self.__register__(fn, self._startup)

    def on_shutdown(self, fn: t.Callable) -> None:
        """Add a function to shutdown."""
        self.__register__(fn, self._shutdown)


class RouterMiddleware(BaseMiddeware):
    """Bind callbacks to HTTP paths."""

    def __init__(self, app: ASGIApp = None, router: Router = None) -> None:
        """Initialize HTTP router. """
        super(RouterMiddleware, self).__init__(app)
        self.router = router or Router()

    async def __process__(self, scope: Scope, receive: Receive, send: Send):
        """Get an app and process."""
        app, path_params = self.__dispatch__(scope)
        scope['path_params'] = path_params
        return await app(scope, receive, send)

    def __dispatch__(self, scope: Scope) -> t.Tuple[t.Callable, t.Mapping]:
        """Lookup for a callback."""
        try:
            return self.router(scope.get("root_path", "") + scope["path"], scope['method'])
        except self.router.NotFound:
            return self.app, {}


class StaticFilesMiddleware(BaseMiddeware):
    """Serve static files."""

    def __init__(self, app: ASGIApp = None, url_prefix: str = '/static',
                 folders: t.Union[str, t.List[str]] = None) -> None:
        """Initialize the middleware. """
        super(StaticFilesMiddleware, self).__init__(app)
        self.url_prefix = url_prefix
        folders = folders or []
        if isinstance(folders, str):
            folders = [folders]
        self.folders: t.List[Path] = [Path(folder) for folder in folders]

    async def __process__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve static files for self url prefix."""
        if not self.folders or not scope['path'].startswith(self.url_prefix):
            return await self.app(scope, receive, send)

        filename = scope['path'][len(self.url_prefix):].strip('/')
        for folder in self.folders:
            filepath = folder.joinpath(filename).resolve()
            try:
                response: t.Optional[Response] = ResponseFile(
                    filepath, headers_only=scope['method'] == 'HEAD')
                break

            except ASGIError:
                response = None

        response = response or ResponseError(404)

        async for msg in response:
            await send(msg)
