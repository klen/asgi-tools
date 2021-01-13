"""Application Tests."""

from pathlib import Path

from asgi_lifespan import LifespanManager


async def test_app(client):
    from asgi_tools.app import App, ResponseError

    app = App(static_folders=[Path(__file__).parent])

    @app.route('/test/{param}', methods='get')
    async def test_request(request):
        return "Done %s" % request.matches['param']

    @app.route('/data', methods='post')
    async def test_data(request):
        data = await request.data()
        return dict(data)

    @app.route('/error')
    async def test_unhandled_exception(request):
        raise RuntimeError('An exception')

    @app.route('/502')
    async def test_response_error(request):
        raise ResponseError(502)

    @app.middleware
    async def simple_md(app, request, *args):
        response = await app(request, *args)
        if response:
            response.headers['x-simple'] = 42
        return response

    @app.middleware
    def simple_md2(app):

        async def middleware(request, *args):
            response = await app(request, *args)
            if response and response.status_code == 200 and \
                    response.headers['content-type'].startswith('text'):
                response.content = "Simple %s" % response.content
            return response

        return middleware

    async with LifespanManager(app):
        async with client(app) as req:

            res = await req.get('/test/42')
            assert res.status_code == 200
            assert res.headers['x-simple'] == '42'
            assert res.text == "Simple Done 42"

            res = await req.get('/404')
            assert res.status_code == 404
            assert res.text == "Nothing matches the given URI"

            res = await req.post('/test/42')
            assert res.status_code == 405
            assert res.text == 'Specified method is invalid for this resource'

            res = await req.get('/502')
            assert res.status_code == 502
            assert res.text == "Invalid responses from another server/proxy"

            res = await req.get('/error')
            assert res.status_code == 500
            assert res.text == "Server got itself in trouble"

            res = await req.get('/static/test_app.py')
            assert res.status_code == 200
            assert res.text.startswith('"""Application Tests."""')

            res = await req.post('/data', json={'test': 'passed'})
            assert res.status_code == 200
            assert res.json() == {'test': 'passed'}


async def test_app_static(client):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])

    async with LifespanManager(app):
        async with client(app) as req:

            res = await req.get('/static/test_app.py')
            assert res.status_code == 200
            assert res.text.startswith('"""Application Tests."""')


async def test_app_handle_exception(client):
    from asgi_tools.app import App, ASGINotFound

    app = App()

    @app.on_exception(Exception)
    async def handle_unknown(exc):
        return 'UNKNOWN: %s' % exc

    @app.on_exception(ASGINotFound)
    async def handle_response_error(exc):
        return 'Response 404'

    @app.route('/500')
    async def raise_unknown(request):
        raise Exception('Unknown Exception')

    async with LifespanManager(app):
        async with client(app) as req:

            res = await req.get('/500')
            assert res.status_code == 200
            assert res.text == 'UNKNOWN: Unknown Exception'

            res = await req.get('/404')
            assert res.status_code == 200
            assert res.text == 'Response 404'


async def test_cbv(app, client):
    from asgi_tools.app import App, HTTPView

    app = App()

    @app.route('/cbv')
    class Custom(HTTPView):

        async def get(self, request):
            return 'CBV: get'

        async def post(self, request):
            return 'CBV: post'

    async with client(app) as req:

        res = await req.get('/cbv')
        assert res.status_code == 200
        assert res.text == 'CBV: get'

        res = await req.post('/cbv')
        assert res.status_code == 200
        assert res.text == 'CBV: post'

        res = await req.put('/cbv')
        assert res.status_code == 405
