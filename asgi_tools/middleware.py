from asyncio import iscoroutine

from . import SUPPORTED_SCOPES
from .request import Request
from .response import Response, PlainTextResponse, HTMLResponse, JSONResponse
from .utils import to_coroutine


async def parse_response(response):

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

    scopes = {'http', 'websockets'}

    def __init__(self, app, **kwargs):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] in self.scopes:
            return await self.process(scope, receive, send)

        return await self.app(scope, receive, send)

    async def process(self, scope, receive, send):
        raise NotImplementedError()


class RequestMiddleware(BaseMiddeware):

    async def process(self, scope, receive, send):
        scope['request'] = Request(scope, receive, send)
        return await self.app(scope, receive, send)


class ResponseMiddleware(BaseMiddeware):

    async def process(self, scope, receive, send):
        res = await self.app(scope, receive, send)
        if res:
            res = await parse_response(res)
            await res(scope, receive, send)


class LifespanMiddleware(BaseMiddeware):

    scopes = {'lifespan'}

    def __init__(self, app, on_startup=None, on_shutdown=None, **kwargs):
        super(LifespanMiddleware, self).__init__(app, **kwargs)
        self._startup = []
        self._shutdown = []
        self.register(on_startup, self._startup)
        self.register(on_shutdown, self._shutdown)

    async def process(self, scope, receive, send):
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                await self.startup(scope)
                await send({'type': 'lifespan.startup.complete'})

            elif message['type'] == 'lifespan.shutdown':
                await self.shutdown(scope)
                return await send({'type': 'lifespan.shutdown.complete'})

    def register(self, handlers, container):
        if not handlers:
            return

        if not isinstance(handlers, list):
            handlers = [handlers]

        container += [to_coroutine(fn) for fn in handlers]
        return container

    def on_startup(self, fn):
        self.register(fn, self._startup)

    def on_shutdown(self, fn):
        self.register(fn, self._shutdown)

    async def startup(self, scope):
        for fn in self._startup:
            await fn()

    async def shutdown(self, scope):
        for fn in self._shutdown:
            await fn()


class RouterMiddleware(BaseMiddeware):

    def __init__(self, app, routes=None, **kwargs):
        super(RouterMiddleware, self).__init__(app, **kwargs)
        self.routes = routes or {}

    async def process(self, scope, receive, send):
        app = self.dispatch(scope)
        return await app(scope, receive, send)

    def dispatch(self, scope):
        path = scope.get("root_path", "") + scope["path"]
        return self.routes.get(path) or self.app

    def route(self, path):
        def decorator(fn):
            self.routes[path.strip()] = to_coroutine(fn)
            return fn

        return decorator


class AppMiddleware(LifespanMiddleware, RouterMiddleware):

    def __init__(self, app=None, **kwargs):
        if not app:
            async def app(request):
                return Response('Not Found', status_code=404)

        super(AppMiddleware, self).__init__(app, **kwargs)

    async def __call__(self, scope, receive, send):
        if scope['type'] not in SUPPORTED_SCOPES:
            return await super().__call__(scope, receive, send)

        request = Request(scope, receive, send)
        app = self.dispatch(scope)
        response = await app(request)
        app = await parse_response(response)
        await app(scope, receive, send)


def combine(app, *middlewares):
    for md in list(middlewares)[::-1]:
        app = md(app)

    return app
