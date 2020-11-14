"""test middlewares"""

from httpx import AsyncClient


async def test_response_middleware():
    from asgi_tools import ResponseMiddleware

    # Test default response
    app = ResponseMiddleware()
    async with AsyncClient(
            app=app, base_url='http://testserver') as client:
        res = await client.get('/')
        assert res.status_code == 404
        assert res.text == 'Not Found'


async def test_request_response_middlewares():
    from asgi_tools import RequestMiddleware, ResponseMiddleware, combine

    async def app(request, receive, send):
        data = await request.form()
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = combine(app, ResponseMiddleware, RequestMiddleware)

    async with AsyncClient(
            app=app, base_url='http://testserver') as client:
        res = await client.post(
            '/testurl?last_name=Daniels',
            json={'first_name': 'Jack'},
            headers={'test-header': 'test-value'},
            cookies={'session': 'test-session'})
        assert res.status_code == 200
        assert res.text == "Hello Jack Daniels from '/testurl'"
        assert res.headers['content-length'] == str(len(res.text))


async def test_lifespan_middlewares():
    from asgi_lifespan import LifespanManager
    from asgi_tools import LifespanMiddleware

    events = {}

    app = LifespanMiddleware(
        lambda scope, receive, send: None,
        on_startup=lambda: events.setdefault('started', True),
        on_shutdown=lambda: events.setdefault('finished', True)
    )

    async with LifespanManager(app):
        assert events['started']

    assert events['finished']


async def test_router_middlewares():
    from asgi_tools import RouterMiddleware, ResponseMiddleware

    async def page1(scope, receive, send):
        return 'page1'

    async def page2(scope, receive, send):
        return 'page2'

    app = ResponseMiddleware(RouterMiddleware(routes={'/page1': page1, '/page2': page2}))

    async with AsyncClient(app=app, base_url='http://testserver') as client:
        res = await client.get('/')
        assert res.text == 'Not Found'
        assert res.status_code == 404

        res = await client.get('/page1')
        assert res.status_code == 200
        assert res.text == 'page1'

        res = await client.get('/page2')
        assert res.status_code == 200
        assert res.text == 'page2'


async def test_app_middleware():
    from asgi_lifespan import LifespanManager
    from asgi_tools import AppMiddleware

    events = {}
    app = AppMiddleware(
        on_startup=lambda: events.setdefault('started', True),
        on_shutdown=lambda: events.setdefault('finished', True)
    )

    @app.route('/testurl')
    async def test_request(request, **kwargs):
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url='http://testserver') as client:
            res = await client.post(
                '/testurl?last_name=Daniels',
                json={'first_name': 'Jack'},
                headers={'test-header': 'test-value'},
                cookies={'session': 'test-session'})
            assert res.status_code == 200
            assert res.text == "Hello Jack Daniels from '/testurl'"
            assert res.headers['content-length'] == str(len(res.text))

            res = await client.get('/404')
            assert res.status_code == 404
            assert res.text == "Not Found"

    assert events['started']
    assert events['finished']

    def simple_md(app, **params):
        """The middleware requires request and response."""

        async def middleware(request, receive, send):
            response = await app(request, receive, send)
            if request.url.path == '/custom':
                response.content += ' -- Custom middleware'

            return response

        return middleware

    async def app(request, **kwargs):
        return 'OK'

    app = AppMiddleware(app, simple_md)
    async with AsyncClient(app=app, base_url='http://testserver') as client:
        res = await client.post('/')
        assert res.text == 'OK'

        res = await client.post('/custom')
        assert res.text == 'OK -- Custom middleware'


async def test_multipart():
    from asgi_tools import AppMiddleware

    async def app(request, *args, **kwargs):
        data = await request.form()
        return data['test'].split(b'\n')[0]

    app = AppMiddleware(app)
    async with AsyncClient(app=app, base_url="https://testserver") as client:
        res = await client.post('/', files={'test': open(__file__)})
        assert res.status_code == 200
        assert res.text == '"""test middlewares"""'
        assert res.headers['content-length'] == str(len(res.text))
