from asgi_lifespan import LifespanManager


async def test_app(client):
    from asgi_tools.app import App

    app = App()

    @app.route('/test')
    async def test_request(request, **kwargs):
        return "Done"

    @app.middleware
    async def simple_md(handler, request, *args):
        response = await handler(request, *args)
        response.headers['x-simple'] = 42
        return response

    @app.middleware
    async def simple_md2(handler, request, *args):
        response = await handler(request, *args)
        response.content = "Simple %s" % response.content
        return response

    async with LifespanManager(app):
        async with client(app) as req:
            res = await req.get('/test')
            assert res.status_code == 200
            assert res.headers['x-simple'] == '42'
            assert res.text == "Simple Done"

            res = await req.get('/404')
            assert res.status_code == 404
