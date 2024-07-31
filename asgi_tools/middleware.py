"""ASGI-Tools Middlewares."""

from __future__ import annotations

import abc
from contextlib import suppress
from contextvars import ContextVar
from functools import partial
from inspect import isawaitable
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Final, Mapping, Optional, Union

from http_router import Router

from .errors import ASGIError
from .logs import logger
from .request import Request
from .response import Response, ResponseError, ResponseFile, ResponseRedirect, parse_response
from .utils import to_awaitable

if TYPE_CHECKING:
    from .types import TASGIApp, TASGIMessage, TASGIReceive, TASGIScope, TASGISend


class BaseMiddeware(metaclass=abc.ABCMeta):
    """Base class for ASGI-Tools middlewares."""

    scopes: tuple[str, ...] = ("http", "websocket")

    def __init__(self, app: Optional[TASGIApp] = None) -> None:
        """Save ASGI App."""
        self.bind(app)

    def __call__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend) -> Awaitable:
        """Handle ASGI call."""
        if scope["type"] in self.scopes:
            return self.__process__(scope, receive, send)

        return self.app(scope, receive, send)

    @abc.abstractmethod
    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Do the middleware's logic."""
        raise NotImplementedError()

    @classmethod
    def setup(cls, **params) -> Callable:
        """Setup the middleware without an initialization."""
        return partial(cls, **params)  # type: ignore[abstract]

    def bind(self, app: Optional[TASGIApp] = None):
        """Rebind the middleware to an ASGI application if it has been inited already."""
        self.app = app or ResponseError.NOT_FOUND()
        return self


class ResponseMiddleware(BaseMiddeware):
    """Automatically convert ASGI_ apps results into responses :class:`~asgi_tools.Response` and
    send them to server as ASGI_ messages.

    .. code-block:: python

        from asgi_tools import ResponseMiddleware, ResponseText, ResponseRedirect

        async def app(scope, receive, send):
            # ResponseMiddleware catches ResponseError, ResponseRedirect and convert the exceptions
            # into HTTP response
            if scope['path'] == '/user':
                raise ResponseRedirect('/login')

            # Return ResponseHTML
            if scope['method'] == 'GET':
                return '<b>HTML is here</b>'

            # Return ResponseJSON
            if scope['method'] == 'POST':
                return {'json': 'here'}

            # Return any response explicitly
            if scope['method'] == 'PUT':
                return ResponseText('response is here')

            # Short form to responses: (status_code, body) or (status_code, body, headers)
            return 405, 'Unknown method'

        app = ResponseMiddleware(app)

    The conversion rules:

    * :class:`Response` objects will be directly returned from the view
    * ``dict``, ``list``, ``int``, ``bool``, ``None`` results will be converted
      into :class:`ResponseJSON`
    * ``str``, ``bytes`` results will be converted into :class:`ResponseHTML`
    * ``tuple[int, Any, dict]`` will be converted into a :class:`Response` with
      ``int`` status code, ``dict`` will be used as headers, ``Any`` will be used
      to define the response's type

    .. code-block:: python

        from asgi_tools import ResponseMiddleware

        # The result will be converted into HTML 404 response with the 'Not Found' body
        async def app(request, receive, send):
            return 404, 'Not Found'

        app = ResponseMiddleware(app)

    You are able to raise :class:`ResponseError` from yours ASGI_ apps and it
    will be catched and returned as a response

    """

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Parse responses from callbacks."""
        try:
            result = await self.app(scope, receive, self.send)
            response = parse_response(result)
            await response(scope, receive, send)

        except (ResponseError, ResponseRedirect) as exc:
            await exc(scope, receive, send)

    def send(self, _: TASGIMessage):
        raise RuntimeError("You can't use send() method in ResponseMiddleware")  # noqa: TRY003

    def bind(self, app: Optional[TASGIApp] = None):
        """Rebind the middleware to an ASGI application if it has been inited already."""
        self.app = app or to_awaitable(lambda *_: ResponseError.NOT_FOUND())
        return self


class RequestMiddleware(BaseMiddeware):
    """Automatically create :class:`asgi_tools.Request` from the scope and pass it to ASGI_ apps.

    .. code-block:: python

        from asgi_tools import RequestMiddleware, Response

        async def app(request, receive, send):
            content = f"{ request.method } { request.url.path }"
            response = Response(content)
            await response(scope, receive, send)

        app = RequestMiddleware(app)

    """

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Replace scope with request object."""
        return await self.app(Request(scope, receive, send), receive, send)


class LifespanMiddleware(BaseMiddeware):
    """Manage ASGI_ Lifespan events.

    :param ignore_errors: Ignore errors from startup/shutdown handlers
    :param on_startup: the list of callables to run when the app is starting
    :param on_shutdown: the list of callables to run when the app is finishing

    .. code-block:: python

        from asgi_tools import LifespanMiddleware, Response

        async def app(scope, receive, send):
            response = Response('OK')
            await response(scope, receive, send)

        app = lifespan = LifespanMiddleware(app)

        @lifespan.on_startup
        async def start():
            print('The app is starting')

        @lifespan.on_shutdown
        async def start():
            print('The app is finishing')

    Lifespan middleware may be used as an async context manager for testing purposes

    .. code-block: python

        async def test_my_app():

            # ...

            # Registered startup/shutdown handlers will be called
            async with lifespan:
                # ... do something

    """

    scopes = ("lifespan",)

    def __init__(
        self,
        app: Optional[TASGIApp] = None,
        *,
        logger=logger,
        ignore_errors: bool = False,
        on_startup: Union[Callable, list[Callable], None] = None,
        on_shutdown: Union[Callable, list[Callable], None] = None,
    ) -> None:
        """Prepare the middleware."""
        super(LifespanMiddleware, self).__init__(app)
        self.ignore_errors = ignore_errors
        self.logger = logger
        self.__startup__: list[Callable] = []
        self.__shutdown__: list[Callable] = []
        self.__register__(on_startup, self.__startup__)
        self.__register__(on_shutdown, self.__shutdown__)

    async def __process__(self, _: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Manage lifespan cycle."""
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                msg = await self.run("startup", send)
                await send(msg)

            elif message["type"] == "lifespan.shutdown":
                msg = await self.run("shutdown", send)
                await send(msg)
                break

    def __register__(
        self, handlers: Union[Callable, list[Callable], None], container: list[Callable]
    ) -> None:
        """Register lifespan handlers."""
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += handlers

    async def __aenter__(self):
        """Use the lifespan middleware as a context manager."""
        await self.run("startup")
        return self

    async def __aexit__(self, *_):
        """Use the lifespan middleware as a context manager."""
        await self.run("shutdown")

    async def run(self, event: str, _: Optional[TASGISend] = None):
        """Run startup/shutdown handlers."""
        assert event in {"startup", "shutdown"}
        handlers = getattr(self, f"__{event}__")

        for handler in handlers:
            try:
                res = handler()
                if isawaitable(res):
                    await res

            except Exception as exc:  # noqa: PERF203
                self.logger.exception("%s method '%s' raises an exception.", event.title(), handler)
                if self.ignore_errors:
                    continue

                self.logger.exception("Lifespans process failed")
                return {"type": f"lifespan.{event}.failed", "message": str(exc)}

        return {"type": f"lifespan.{event}.complete"}

    def on_startup(self, fn: Callable) -> None:
        """Add a function to startup."""
        self.__register__(fn, self.__startup__)

    def on_shutdown(self, fn: Callable) -> None:
        """Add a function to shutdown."""
        self.__register__(fn, self.__shutdown__)


class RouterMiddleware(BaseMiddeware):
    r"""Manage routing.

    .. code-block:: python

        from asgi_tools import RouterMiddleware, ResponseHTML, ResponseError

        async def default_app(scope, receive, send):
            response = ResponseError.NOT_FOUND()
            await response(scope, receive, send)

        app = router = RouterMiddleware(default_app)

        @router.route('/status', '/stat')
        async def status(scope, receive, send):
            response = ResponseHTML('STATUS OK')
            await response(scope, receive, send)

        # Bind methods
        # ------------
        @router.route('/only-post', methods=['POST'])
        async def only_post(scope, receive, send):
            response = ResponseHTML('POST OK')
            await response(scope, receive, send)

        # Regexp paths
        # ------------
        import re

        @router.route(re.compile(r'/\d+/?'))
        async def num(scope, receive, send):
            num = int(scope['path'].strip('/'))
            response = ResponseHTML(f'Number { num }')
            await response(scope, receive, send)

        # Dynamic paths
        # -------------

        @router.route('/hello/{name}')
        async def hello(scope, receive, send):
            name = scope['path_params']['name']
            response = ResponseHTML(f'Hello { name.title() }')
            await response(scope, receive, send)

        # Set regexp for params
        @router.route(r'/multiply/{first:\d+}/{second:\d+}')
        async def multiply(scope, receive, send):
            first, second = map(int, scope['path_params'].values())
            response = ResponseHTML(str(first * second))
            await response(scope, receive, send)

    Path parameters are made available in the request/scope, as the ``path_params`` dictionary.

    """

    def __init__(self, app: Optional[TASGIApp] = None, router: Optional[Router] = None) -> None:
        """Initialize HTTP router."""
        super().__init__(app)
        self.router = router or Router(validator=callable)

    async def __process__(self, scope: TASGIScope, *args):
        """Get an app and process."""
        app, scope["path_params"] = self.__dispatch__(scope)
        return await app(scope, *args)

    def __dispatch__(self, scope: TASGIScope) -> tuple[Callable, Optional[Mapping]]:
        """Lookup for a callback."""
        path = f"{scope.get('root_path', '')}{scope['path']}"
        try:
            match = self.router(path, scope["method"])

        except self.router.RouterError:
            return self.app, {}

        else:
            return match.target, match.params  # type: ignore[]

    def route(self, *args, **kwargs):
        """Register a route."""
        return self.router.route(*args, **kwargs)


class StaticFilesMiddleware(BaseMiddeware):
    """Serve static files.

    :param url_prefix:  an URL prefix for static files
    :type url_prefix: str, "/static"
    :param folders: Paths to folders with static files
    :type folders: list[str]

    .. code-block:: python

        from asgi_tools import StaticFilesMiddleware, ResponseHTML

        async def app(scope, receive, send):
            response = ResponseHTML('OK)
            await response(scope, receive, send)

        # Files from static folder will be served from /static
        app = StaticFilesMiddleware(app, folders=['static'])

    """

    scopes = ("http",)

    def __init__(
        self,
        app: Optional[TASGIApp] = None,
        url_prefix: str = "/static",
        folders: Optional[list[Union[str, Path]]] = None,
    ) -> None:
        """Initialize the middleware."""
        super().__init__(app)
        self.url_prefix = url_prefix
        folders = folders or []
        self.folders: list[Path] = [Path(folder) for folder in folders]

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend) -> None:
        """Serve static files for self url prefix."""
        path = scope["path"]
        url_prefix = self.url_prefix
        if path.startswith(url_prefix):
            response: Optional[Response] = None
            filename = path[len(url_prefix) :].strip("/")
            for folder in self.folders:
                filepath = folder.joinpath(filename).resolve()
                with suppress(ASGIError):
                    response = ResponseFile(filepath, headers_only=scope["method"] == "HEAD")
                    break

            response = response or ResponseError(status_code=404)
            await response(scope, receive, send)

        else:
            await self.app(scope, receive, send)


BACKGROUND_TASK: Final = ContextVar[Optional[Awaitable]]("background_task", default=None)


class BackgroundMiddleware(BaseMiddeware):
    """Run background tasks.


    .. code-block:: python

        from asgi_tools import BackgroundMiddleware, ResponseText

        async def app(scope, receive, send):
            response = ResponseText('OK)

            # Schedule any awaitable for later execution
            BackgroundMiddleware.set_task(asyncio.sleep(1))

            # Return response immediately
            await response(scope, receive, send)

            # The task will be executed after the response is sent

        app = BackgroundMiddleware(app)

    """

    async def __process__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Run background tasks."""
        await self.app(scope, receive, send)
        bgtask = BACKGROUND_TASK.get()
        if bgtask is not None and isawaitable(bgtask):
            await bgtask

    @staticmethod
    def set_task(task: Awaitable):
        """Set a task for background execution."""
        BACKGROUND_TASK.set(task)
