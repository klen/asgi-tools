"""Application Tests."""

from pathlib import Path


async def test_app(Client):
    from asgi_tools.app import App, ResponseError

    app = App(static_folders=[Path(__file__).parent])

    @app.route('/test/{param}', methods='get')
    async def test_request(request):
        return "Done %s" % request.path_params['param']

    client = Client(app)

    res = await client.get('/404')
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    res = await client.get('/static/test_app.py')
    assert res.status_code == 200
    text = await res.text()
    assert text.startswith('"""Application Tests."""')

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


async def test_trim_last_slach(Client):
    from asgi_tools.app import App

    app = App()
    client = Client(app)

    @app.route('/route1')
    async def route1(request):
        return 'route1'

    @app.route('/route2/')
    async def route2(request):
        return 'route2'

    res = await client.get('/route1')
    assert res.status_code == 200

    res = await client.get('/route2/')
    assert res.status_code == 200

    res = await client.get('/route1/')
    assert res.status_code == 404

    res = await client.get('/route2')
    assert res.status_code == 404

    app = App(trim_last_slash=True)
    client = Client(app)

    @app.route('/route1')
    async def route1(request):
        return 'route1'

    @app.route('/route2/')
    async def route2(request):
        return 'route2'

    res = await client.get('/route1')
    assert res.status_code == 200

    res = await client.get('/route2/')
    assert res.status_code == 200

    res = await client.get('/route1/')
    assert res.status_code == 200

    res = await client.get('/route2')
    assert res.status_code == 200


async def test_app_static(Client):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])
    client = Client(app)

    async with client.lifespan():

        res = await client.get('/static/test_app.py')
        assert res.status_code == 200
        text = await res.text()
        assert text.startswith('"""Application Tests."""')


async def test_app_handle_exception(Client):
    from asgi_tools.app import App, ResponseError

    app = App()

    @app.route('/500')
    async def raise_unknown(request):
        raise Exception('Unknown Exception')

    @app.route('/501')
    async def raise_response_error(request):
        raise ResponseError(501)

    # By default we handle all exceptions as INTERNAL SERVER ERROR 500 Response
    client = Client(app)
    res = await client.get('/500')
    assert res.status_code == 500
    assert await res.text() == 'Server got itself in trouble'

    @app.on_error(Exception)
    async def handle_unknown(exc):
        return 'UNKNOWN: %s' % exc

    @app.on_error(404)
    async def handle_response_error(exc):
        return 'Response 404'

    @app.on_error(ResponseError)
    async def handler(exc):
        return 'Custom Server Error'

    async with client.lifespan():

        res = await client.get('/500')
        assert res.status_code == 200
        assert await res.text() == 'UNKNOWN: Unknown Exception'

        res = await client.get('/404')
        assert res.status_code == 200
        assert await res.text() == 'Response 404'

        res = await client.get('/501')
        assert res.status_code == 200
        assert await res.text() == 'Custom Server Error'


async def test_app_middleware_simple(client, app):
    from asgi_tools import ResponseHTML

    @app.route('/err')
    async def err(request):
        raise RuntimeError('Handle me')

    @app.on_error(Exception)
    async def custom_exc(exc):
        return ResponseHTML('App Exception')

    res = await client.get('/err')
    assert res.status_code == 200
    assert await res.text() == 'App Exception'

    @app.middleware
    async def simple_md(app, request, receive, send):
        try:
            response = await app(request, receive, send)
            response.headers['x-simple-md'] = 'passed'
            return response
        except RuntimeError:
            return ResponseHTML('Middleware Exception')

    res = await client.get('/')
    assert res.status_code == 200
    assert res.headers['x-simple-md'] == 'passed'

    res = await client.get('/404')
    assert res.status_code == 404
    assert 'x-simple-md' not in res.headers

    res = await client.get('/err')
    assert res.status_code == 200
    assert await res.text() == 'Middleware Exception'


#  @pytest.mark.skip
async def test_app_middleware_classic(client, app):
    from asgi_tools import ResponseError, ResponseHTML

    @app.route('/err')
    async def err(request):
        raise RuntimeError('Handle me')

    @app.on_error(Exception)
    async def custom_exc(exc):
        return ResponseHTML('App Exception')

    @app.middleware
    def classic_md(app):
        async def middleware(scope, receive, send):
            if not scope.headers.get('authorization'):
                response = ResponseError.UNAUTHORIZED()
                await response(scope, receive, send)
                return

            try:
                await app(scope, receive, send)
            except RuntimeError:
                response = ResponseHTML('Middleware Exception')
                await response(scope, receive, send)

        return middleware

    res = await client.get('/')
    assert res.status_code == 401

    res = await client.get('/', headers={'authorization': 'any'})
    assert res.status_code == 200
    assert await res.text() == 'OK'

    res = await client.get('/err', headers={'authorization': 'any'})
    assert res.status_code == 200
    assert await res.text() == 'Middleware Exception'


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


async def test_app_lifespan(app, client):

    SIDE_EFFECTS = {}

    @app.on_startup
    def start():
        SIDE_EFFECTS['started'] = True

    @app.on_shutdown
    def finish():
        SIDE_EFFECTS['finished'] = True

    async with client.lifespan():
        assert SIDE_EFFECTS['started']
        res = await client.get('/')
        assert res.status_code == 200


    assert SIDE_EFFECTS['finished']
