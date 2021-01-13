"""test middlewares"""


async def test_response_middleware(Client):
    from asgi_tools import ResponseMiddleware, ResponseError

    # Test default response
    app = ResponseMiddleware()
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 404
    assert res.text == 'Not Found'

    async def app(*args):
        return False

    app = ResponseMiddleware(app)
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 200
    assert res.text == 'false'

    async def app(*args):
        raise ResponseError(502)

    app = ResponseMiddleware(app)
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 502
    assert res.text == 'Invalid responses from another server/proxy'


async def test_request_response_middlewares(Client):
    from asgi_tools import RequestMiddleware, ResponseMiddleware, combine

    async def app(request, receive, send):
        data = await request.form()
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = combine(app, ResponseMiddleware, RequestMiddleware)

    client = Client(app)
    res = await client.post(
        '/testurl?last_name=Daniels',
        json={'first_name': 'Jack'},
        headers={'test-header': 'test-value'},
        cookies={'session': 'test-session'})
    assert res.status_code == 200
    assert res.text == "Hello Jack Daniels from '/testurl'"
    assert res.headers['content-length'] == str(len(res.text))


async def test_lifespan_middleware():
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


async def test_router_middleware(Client):
    from http_router import Router
    from asgi_tools import RouterMiddleware, ResponseMiddleware

    router = Router()
    app = ResponseMiddleware(RouterMiddleware(router=router))

    @router.route('/page1')
    async def page1(scope, receive, send):
        return 'page1'

    @router.route('/page2/{mode}')
    async def page2(scope, receive, send):
        mode = scope['matches']['mode']
        return f'page2: {mode}'

    client = Client(app)
    res = await client.get('/')
    assert res.text == 'Not Found'
    assert res.status_code == 404

    res = await client.get('/page1')
    assert res.status_code == 200
    assert res.text == 'page1'

    res = await client.get('/page2/42')
    assert res.status_code == 200
    assert res.text == 'page2: 42'


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
    assert not res.text

    res = await client.get('/static/test_middlewares.py')
    assert res.status_code == 200
    assert res.text.startswith('"""test middlewares"""')

    res = await client.get('/static/unknown')
    assert res.status_code == 404

import pytest

@pytest.mark.skip('not implemented')
async def test_websocket_middleware(Client):
    from asgi_tools import WebSocketMiddleware, ResponseMiddleware

    app = WebSocketMiddleware(ResponseMiddleware())
    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 404

    res = await client.websocket('/')
    breakpoint()
