"""ASGI-Tools tests."""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_request():
    from asgi_tools import Request

    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'GET',
        'headers': [
            (b'host', b'testserver'),
            (b'accept', b'*/*'),
            (b'accept-encoding', b'gzip, deflate'),
            (b'connection', b'keep-alive'),
            (b'user-agent', b'python-httpx/0.16.1'),
            (b'test-header', b'test-value'),
            (b'cookie', b'session=test-session'),
        ],
        'scheme': 'http',
        'path': '/testurl',
        'query_string': b'a=1',
        'server': ('testserver', None),
        'client': ('127.0.0.1', 123),
        'root_path': ''
    }

    async def receive():
        return {'body': b'name=value'}

    request = Request(scope, receive)
    assert request.client == ('127.0.0.1', 123)
    assert request.cookies
    assert request.cookies['session'] == 'test-session'
    assert request.headers['User-Agent'] == 'python-httpx/0.16.1'
    assert request.http_version == '1.1'
    assert request.method == 'GET'
    assert request.query
    assert request.query['a'] == '1'
    assert request.type == 'http'
    assert request.url

    body = await request.body()
    assert body

    formdata = await request.form()
    assert formdata
    assert formdata['name'] == 'value'

    formdata2 = await request.form()
    assert formdata2 is formdata


@pytest.mark.asyncio
async def test_response():
    from asgi_tools import Response, parse_response

    response = Response("Content", content_type='text/html')
    response.cookies['session'] = 'test-session'
    response.cookies['session']['path'] = '/'
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.headers == [
        (b"content-type", b"text/html; charset=utf-8"),
        (b'set-cookie', b'session=test-session; Path=/'),
    ]
    messages = [m for m in response]
    assert messages
    assert messages[0] == {
        'headers': [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'content-length', b'7'),
            (b'set-cookie', b'session=test-session; Path=/'),
        ],
        'status': 200,
        'type': 'http.response.start'
    }
    assert messages[1] == {'body': b'Content', 'type': 'http.response.body'}

    response = await parse_response({'test': 'passed'})
    assert response.status_code == 200
    assert response.headers == [(b'content-type', b'application/json')]
    assert list(response)[1] == {'body': b'{"test": "passed"}', 'type': 'http.response.body'}

    response = await parse_response((500,))
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_response_middleware():
    from asgi_tools import ResponseMiddleware

    # Test default response
    app = ResponseMiddleware()
    async with AsyncClient(
            app=app, base_url='http://testserver') as client:
        res = await client.get('/')
        assert res.status_code == 200
        assert res.text == 'Default response from ASGI-Tools'


@pytest.mark.asyncio
async def test_request_response_middlewares():
    from asgi_tools import RequestMiddleware, ResponseMiddleware, combine

    async def app(scope, receive, send):
        request = scope['request']
        data = await request.form()
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = combine(app, RequestMiddleware, ResponseMiddleware)

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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_router_middlewares():
    from asgi_tools import RouterMiddleware, Response

    def page1(scope, receive, send):
        return Response('page1')(scope, receive, send)

    def page2(scope, receive, send):
        return Response('page2')(scope, receive, send)

    def index(scope, receive, send):
        return Response('Not Found', 404)(scope, receive, send)

    app = RouterMiddleware(index, routes={'/page1': page1, '/page2': page2})

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


@pytest.mark.asyncio
async def test_app_middleware():
    from asgi_lifespan import LifespanManager
    from asgi_tools import AppMiddleware

    async def app(request):
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    events = {}
    app = AppMiddleware(
        app,
        on_startup=lambda: events.setdefault('started', True),
        on_shutdown=lambda: events.setdefault('finished', True)
    )

    @app.route('/hello/{name}', methods="post")
    async def hello(request, name=None, **kwargs):
        breakpoint()
        pass

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

    assert events['started']
    assert events['finished']


@pytest.mark.asyncio
async def test_multipart():
    from asgi_tools import AppMiddleware

    async def app(request):
        data = await request.form()
        return data['test'].split(b'\n')[0]

    app = AppMiddleware(app)
    async with AsyncClient(app=app, base_url="https://testserver") as client:
        res = await client.post('/', files={'test': open(__file__)})
        assert res.status_code == 200
        assert res.text == '"""ASGI-Tools tests."""'
        assert res.headers['content-length'] == str(len(res.text))
