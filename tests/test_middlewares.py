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

    async def app(request):
        data = await request.form()
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = combine(app, ResponseMiddleware, RequestMiddleware, pass_request=True)

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

    async def index(scope, receive, send):
        return 404, 'Not Found'

    app = ResponseMiddleware(RouterMiddleware(index, routes={'/page1': page1, '/page2': page2}))

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
    async def test_request(request, *args, **kwargs):
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
