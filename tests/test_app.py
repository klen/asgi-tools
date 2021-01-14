"""Application Tests."""

from pathlib import Path

from asgi_lifespan import LifespanManager


async def test_app(Client):
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

    client = Client(app)

    res = await client.get('/test/42')
    assert res.status_code == 200
    assert res.headers['x-simple'] == '42'
    assert res.text == "Simple Done 42"

    res = await client.get('/404')
    assert res.status_code == 404
    assert res.text == "Nothing matches the given URI"

    res = await client.post('/test/42')
    assert res.status_code == 405
    assert res.text == 'Specified method is invalid for this resource'

    res = await client.get('/502')
    assert res.status_code == 502
    assert res.text == "Invalid responses from another server/proxy"

    res = await client.get('/error')
    assert res.status_code == 500
    assert res.text == "Server got itself in trouble"

    res = await client.get('/static/test_app.py')
    assert res.status_code == 200
    assert res.text.startswith('"""Application Tests."""')

    res = await client.post('/data', json={'test': 'passed'})
    assert res.status_code == 200
    assert res.json() == {'test': 'passed'}


async def test_app_static(Client):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])

    async with LifespanManager(app):
        client = Client(app)

        res = await client.get('/static/test_app.py')
        assert res.status_code == 200
        assert res.text.startswith('"""Application Tests."""')


async def test_app_handle_exception(Client):
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
        client = Client(app)

        res = await client.get('/500')
        assert res.status_code == 200
        assert res.text == 'UNKNOWN: Unknown Exception'

        res = await client.get('/404')
        assert res.status_code == 200
        assert res.text == 'Response 404'


async def test_cbv(app, client):
    from asgi_tools.app import HTTPView

    @app.route('/cbv')
    class Custom(HTTPView):

        async def get(self, request):
            return 'CBV: get'

        async def post(self, request):
            return 'CBV: post'

    res = await client.get('/cbv')
    assert res.status_code == 200
    assert res.text == 'CBV: get'

    res = await client.post('/cbv')
    assert res.status_code == 200
    assert res.text == 'CBV: post'

    res = await client.put('/cbv')
    assert res.status_code == 405


async def test_websockets(app, client):
    from asgi_tools import WebSocketMiddleware

    @app.route('/websocket')
    async def websocket(ws):
        await ws.accept()
        msg = await ws.receive()
        assert msg == 'ping'
        await ws.send('pong')
        await ws.close()

    res = await client.get('/')
    assert res.status_code == 200

    async with client.websocket('/websocket') as ws:
        await ws.send('ping')
        msg = await ws.receive()
        assert msg == 'pong'
