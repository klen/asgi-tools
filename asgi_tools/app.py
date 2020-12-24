from .middleware import (
    LifespanMiddleware, ResponseMiddleware, RequestMiddleware, RouterMiddleware, combine)


class App:

    def __init__(self, *app_middlewares, pass_params_only=True):
        self.app = None
        self.app_middlewares = list(app_middlewares)
        self.lifespan = LifespanMiddleware()
        self.router = RouterMiddleware(pass_params_only=pass_params_only)

    async def __call__(self, scope, receive, send):
        if self.app is None:
            middlewares = []
            app = combine(self.router, *[
                RequestMiddleware, ResponseMiddleware, *self.app_middlewares,
                ResponseMiddleware.setup(prepare_response_only=True)
            ])
            self.app = self.lifespan.bind(app)

        return await self.app(scope, receive, send)

    def insert_middleware(self, md):
        self.app_middlewares.append(md)

    def route(self, *paths, **params):
        return self.router.route(*paths, **params)

    def on_startup(self, fn):
        return self.lifespan.on_startup(fn)

    def on_shutdown(self, fn):
        return self.lifespan.on_shutdown(fn)
