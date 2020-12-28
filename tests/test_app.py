from asgi_lifespan import LifespanManager


async def test_app(client):
    from asgi_tools.app import App, ResponseError

    app = App()

    @app.route('/test')
    async def test_request(request, **kwargs):
        return "Done"

    @app.route('/error')
    async def test_unhandled_exception(request, **kwargs):
        raise RuntimeError('An exception')

    @app.route('/502')
    async def test_response_error(request, **kwargs):
        raise ResponseError(502)

    @app.middleware
    async def simple_md(app, request, *args):
        response = await app(request, *args)
        response.headers['x-simple'] = 42
        return response

    @app.middleware
    def simple_md2(app):

        async def middleware(request, *args):
            response = await app(request, *args)
            if response.status_code == 200:
                response.content = "Simple %s" % response.content
            return response

        return middleware

    async with LifespanManager(app):
        async with client(app) as req:
            res = await req.get('/test')
            assert res.status_code == 200
            assert res.headers['x-simple'] == '42'
            assert res.text == "Simple Done"

            res = await req.get('/404')
            assert res.status_code == 404
            assert res.text == "Nothing matches the given URI"

            res = await req.get('/502')
            assert res.status_code == 502
            assert res.text == "Invalid responses from another server/proxy"

            res = await req.get('/error')
            assert res.status_code == 500
            assert res.text == "Server got itself in trouble"
