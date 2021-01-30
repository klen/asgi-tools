"""Application Tests."""

from pathlib import Path

from asgi_lifespan import LifespanManager


async def test_app(Client):
    from asgi_tools.app import App, ResponseError

    app = App(static_folders=[Path(__file__).parent])

    @app.route('/test/{param}', methods='get')
    async def test_request(request):
        return "Done %s" % request.path_params['param']

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

    res = await client.get('/404')
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    res = await client.get('/static/test_app.py')
    assert res.status_code == 200
    text = await res.text()
    assert text.startswith('"""Application Tests."""')

    res = await client.get('/test/42')
    assert res.status_code == 200
    assert res.headers['x-simple'] == '42'
    assert await res.text() == "Simple Done 42"

    res = await client.post('/test/42')
    assert res.status_code == 405
    assert await res.text() == 'Specified method is invalid for this resource'

    @app.route('/502')
    async def test_response_error(request):
        raise ResponseError.BAD_GATEWAY()

    res = await client.get('/502')
    assert res.status_code == 502
    assert await res.text() == "Invalid responses from another server/proxy"

    @app.route('/error')
    async def test_unhandled_exception(request):
        raise RuntimeError('An exception')

    res = await client.get('/error')
    assert res.status_code == 500
    assert await res.text() == "Server got itself in trouble"

    @app.route('/data', methods='post')
    async def test_data(request):
        data = await request.data()
        return dict(data)

    res = await client.post('/data', json={'test': 'passed'})
    assert res.status_code == 200
    assert await res.json() == {'test': 'passed'}

    @app.route('/none')
    async def test_none(request):
        return

    res = await client.get('/none')
    assert res.status_code == 200

    @app.route('/path_params')
    async def path_params(request):
        return request['path_params'].get('unknown', 42)

    res = await client.get('/path_params')
    assert res.status_code == 200
    assert await res.text() == '42'


async def test_app_static(Client):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])

    async with LifespanManager(app):
        client = Client(app)

        res = await client.get('/static/test_app.py')
        assert res.status_code == 200
        text = await res.text()
        assert text.startswith('"""Application Tests."""')


async def test_app_handle_exception(Client):
    from asgi_tools.app import App, ASGINotFound, ResponseError

    app = App()

    @app.on_exception(Exception)
    async def handle_unknown(exc):
        return 'UNKNOWN: %s' % exc

    @app.on_exception(ASGINotFound)
    async def handle_response_error(exc):
        return 'Response 404'

    @app.on_exception(ResponseError)
    async def handler(exc):
        return 'Custom Server Error'

    @app.route('/500')
    async def raise_unknown(request):
        raise Exception('Unknown Exception')

    @app.route('/501')
    async def raise_response_error(request):
        raise ResponseError(501)

    async with LifespanManager(app):
        client = Client(app)

        res = await client.get('/500')
        assert res.status_code == 200
        assert await res.text() == 'UNKNOWN: Unknown Exception'

        res = await client.get('/404')
        assert res.status_code == 200
        assert await res.text() == 'Response 404'

        res = await client.get('/501')
        assert res.status_code == 200
        assert await res.text() == 'Custom Server Error'


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
    assert await res.text() == 'CBV: get'

    res = await client.post('/cbv')
    assert res.status_code == 200
    assert await res.text() == 'CBV: post'

    res = await client.put('/cbv')
    assert res.status_code == 405


async def test_websockets(app, client):
    from asgi_tools import ResponseWebSocket

    @app.route('/websocket')
    async def websocket(request):
        ws = ResponseWebSocket(request)
        await ws.accept()
        msg = await ws.receive()
        assert msg == 'ping'
        await ws.send('pong')
        await ws.close()

    async with client.websocket('/websocket') as ws:
        await ws.send('ping')
        msg = await ws.receive()
        assert msg == 'pong'

    res = await client.get('/')
    assert res.status_code == 200
