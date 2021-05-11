"""test middlewares"""


async def test_response_middleware(Client):
    from asgi_tools import ResponseMiddleware, ResponseError

    # Test default response
    app = ResponseMiddleware()
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 404
    assert await res.text() == 'Not Found'

    async def app(*args):
        return False

    app = ResponseMiddleware(app)
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == 'false'

    async def app(*args):
        raise ResponseError.BAD_GATEWAY()

    app = ResponseMiddleware(app)
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 502
    assert await res.text() == 'Invalid responses from another server/proxy'


async def test_request_response_middlewares(Client):
    from asgi_tools import RequestMiddleware, ResponseMiddleware

    async def app(request, receive, send):
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = RequestMiddleware(ResponseMiddleware(app))

    client = Client(app)
    res = await client.post(
        '/testurl?last_name=Daniels',
        json={'first_name': 'Jack'},
        headers={'test-header': 'test-value'},
        cookies={'session': 'test-session'})
    assert res.status_code == 200
    assert await res.text() == "Hello Jack Daniels from '/testurl'"
    assert res.headers['content-length'] == str(len("Hello Jack Daniels from '/testurl'"))


async def test_lifespan_middleware(Client):
    from asgi_tools import LifespanMiddleware

    SIDE_EFFECTS = {}

    async def fail():
        raise Exception

    async def start():
        SIDE_EFFECTS['started'] = True

    app = LifespanMiddleware(
        lambda scope, receive, send: None,
        on_startup=[fail, start],
        on_shutdown=lambda: SIDE_EFFECTS.setdefault('finished', True)
    )
    client = Client(app)

    async with client.lifespan():
        assert 'started' not in SIDE_EFFECTS

    assert 'finished' not in SIDE_EFFECTS

    app = LifespanMiddleware.setup(ignore_errors=True)(
        lambda scope, receive, send: None,
        on_startup=[fail, start],
        on_shutdown=lambda: SIDE_EFFECTS.setdefault('finished', True)
    )
    client = Client(app)

    async with client.lifespan():
        assert SIDE_EFFECTS['started']

    assert SIDE_EFFECTS['finished']


async def test_router_middleware(Client):
    from asgi_tools import RouterMiddleware, ResponseMiddleware

    router = RouterMiddleware()
    app = ResponseMiddleware(router)

    @router.route('/page1')
    async def page1(scope, receive, send):
        return 'page1'

    @router.route('/page2/{mode}', methods=['POST'])
    async def page2(scope, receive, send):
        mode = scope['path_params']['mode']
        return f'page2: {mode}'

    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 404
    assert await res.text() == 'Not Found'

    res = await client.get('/page1')
    assert res.status_code == 200
    assert await res.text() == 'page1'

    res = await client.get('/page2/42')
    assert res.status_code == 404  # Returns default application

    res = await client.post('/page2/42')
    assert res.status_code == 200
    assert await res.text() == 'page2: 42'


async def test_staticfiles_middleware(Client, app):
    import os
    from asgi_tools import StaticFilesMiddleware

    app = StaticFilesMiddleware(app, folders=['/', os.path.dirname(__file__)])

    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 200

    res = await client.head('/static/test_middlewares.py')
    assert res.status_code == 200
    assert res.headers['content-type'] == 'text/x-python'
    assert not await res.text()

    res = await client.get('/static/test_middlewares.py')
    assert res.status_code == 200
    text = await res.text()
    assert text.startswith('"""test middlewares"""')

    res = await client.get('/static/unknown')
    assert res.status_code == 404
