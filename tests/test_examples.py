import re


async def test_readme_request_response(Client):

    # Example
    import json
    from asgi_tools import Request, Response

    async def app(scope, receive, send):
        if scope['type'] != 'http':
            return

        # Parse scope
        request = Request(scope, receive, send)
        request_data = {

            # Get full URL
            "url": str(request.url),

            "charset": request.charset,

            # Get headers
            "headers": {**request.headers},

            # Get query params
            "query": dict(request.url.query),

            # Get cookies
            "cookies": dict(request.cookies),

        }

        # Create a response (HTMLResponse, PlainTextResponse, JSONResponse, StreamResponse,
        # RedirectResponse also available)
        response = Response(json.dumps(request_data), content_type="application/json")

        # Send ASGI messages
        return await response(scope, receive, send)

    # Test
    client = Client(app)

    res = await client.get('/test?var=42')
    assert res.status_code == 200
    data = await res.json()
    assert data['url'] == 'http://localhost/test?var=42'
    assert data['query'] == {'var': '42'}


async def test_readme_request_response_middleware(Client):

    # Example
    from asgi_tools import RequestMiddleware, ResponseHTML

    async def app(request, receive, send):
        # We will get a parsed request here
        data = await request.json()
        response = ResponseHTML(data['name'])
        return await response(request, receive, send)

    app = RequestMiddleware(app)

    # Test
    client = Client(app)
    res = await client.post('/test', json={'name': 'passed'})
    assert res.status_code == 200
    assert await res.text() == 'passed'

    # Example
    from asgi_tools import ResponseMiddleware

    async def app(request, receive, send):
        return "Hello World!"

    app = ResponseMiddleware(app)

    # Test
    client = Client(app)
    res = await client.post('/test', json={'name': 'passed'})
    assert res.status_code == 200
    assert res.headers['content-type'] == 'text/html; charset=utf-8'
    assert await res.text() == 'Hello World!'


async def test_readme_router_middleware():
    from http_router import Router

    router = Router()

    @router.route('/page1')
    async def page1(request, receive, send):
        return 'page1'

    @router.route('/page2')
    async def page2(request, receive, send):
        return 'page2'


async def test_docs(Client):
    from asgi_tools import App

    app = App()

    @app.route('/')
    async def hello_world(request):
        return "<p>Hello, World!</p>"

    client = Client(app)

    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == "<p>Hello, World!</p>"


async def test_docs_response_redirect(Client):
    from asgi_tools import ResponseRedirect

    async def app(scope, receive, send):
        response = ResponseRedirect('/login')
        await response(scope, receive, send)

    client = Client(app)

    res = await client.get('/', follow_redirect=False)
    assert res.status_code == 307
    assert res.headers['location'] == '/login'

    from asgi_tools import Request, ResponseMiddleware

    async def app(scope, receive, send):
        request = Request(scope, receive)
        if not request.headers.get('authorization'):
            raise ResponseRedirect('/login')

        return 'OK'

    app = ResponseMiddleware(app)
    client = Client(app)

    res = await client.get('/', follow_redirect=False)
    assert res.status_code == 307
    assert res.headers['location'] == '/login'

    res = await client.get('/', follow_redirect=False, headers={'authorization': 'user'})
    assert res.status_code == 200
    assert await res.text() == 'OK'


async def test_docs_response_error(Client):
    from asgi_tools import ResponseError

    async def app(scope, receive, send):
        response = ResponseError('Timeout', 502)
        await response(scope, receive, send)

    client = Client(app)

    res = await client.get('/')
    assert res.status_code == 502
    assert await res.text() == 'Timeout'

    from asgi_tools import ResponseError, Request, ResponseMiddleware

    async def app(scope, receive, send):
        request = Request(scope, receive)
        if not request.method == 'POST':
            raise ResponseError('Invalid request data', 400)

        return 'OK'

    app = ResponseMiddleware(app)
    client = Client(app)

    res = await client.get('/')
    assert res.status_code == 400
    assert await res.text() == 'Invalid request data'

    res = await client.post('/')
    assert res.status_code == 200


async def test_docs_response_stream(Client):
    from asgi_tools import ResponseStream
    from asgi_tools._compat import aio_sleep  # for compatability with different async libs

    async def stream_response():
        for number in range(10):
            await aio_sleep(1e-2)
            yield str(number)

    async def app(scope, receive, send):
        response = ResponseStream(stream_response(), content_type='plain/text')

        await response(scope, receive, send)
    client = Client(app)

    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == '0123456789'


async def test_docs_response_middleware(Client):
    from asgi_tools import ResponseMiddleware, ResponseText, ResponseRedirect

    async def app(scope, receive, send):
        # ResponseMiddleware catches ResponseError, ResponseRedirect and convert the exceptions
        # into HTTP response
        if scope['path'] == '/user':
            raise ResponseRedirect('/login')

        # Return ResponseHTML
        if scope['method'] == 'GET':
            return '<b>HTML is here</b>'

        # Return ResponseJSON
        if scope['method'] == 'POST':
            return {'json': 'here'}

        # Return any response explicitly
        if scope['method'] == 'PUT':
            return ResponseText('response is here')

        # Short form to responses: (status_code, body) or (status_code, body, headers)
        return 405, 'Unknown method'

    app = ResponseMiddleware(app)
    client = Client(app)

    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == '<b>HTML is here</b>'

    res = await client.post('/')
    assert res.status_code == 200
    assert await res.json() == {'json': 'here'}

    res = await client.put('/')
    assert res.status_code == 200
    assert res.headers['content-type'] == 'text/plain; charset=utf-8'
    assert await res.text() == 'response is here'

    res = await client.get('/user', follow_redirect=False)
    assert res.status_code == 307

    res = await client.delete('/')
    assert res.status_code == 405


async def test_docs_router_middleware(Client):
    from asgi_tools import RouterMiddleware, ResponseHTML, ResponseError

    async def default_app(scope, receive, send):
        response = ResponseError.NOT_FOUND()
        await response(scope, receive, send)

    app = router = RouterMiddleware(default_app)

    @router.route('/status')
    async def status(scope, receive, send):
        response = ResponseHTML('STATUS OK')
        await response(scope, receive, send)

    # Bind methods
    # ------------
    @router.route('/only-post', methods=['POST'])
    async def only_post(scope, receive, send):
        response = ResponseHTML('POST OK')
        await response(scope, receive, send)

    # Regexp paths
    # ------------

    @router.route(re.compile(r'/\d+/?'))
    async def num(scope, receive, send):
        num = int(scope['path'].strip('/'))
        response = ResponseHTML(f'Number { num }')
        await response(scope, receive, send)

    # Dynamic paths
    # -------------

    @router.route('/hello/{name}')
    async def hello(scope, receive, send):
        name = scope['path_params']['name']
        response = ResponseHTML(f'Hello { name.title() }')
        await response(scope, receive, send)

    # Set regexp for params
    @router.route(r'/multiply/{first:int}/{second:int}')
    async def multiply(scope, receive, send):
        first, second = map(int, scope['path_params'].values())
        response = ResponseHTML(str(first * second))
        await response(scope, receive, send)

    client = Client(app)

    res = await client.get('/unknown')
    assert res.status_code == 404

    res = await client.post('/status')
    assert res.status_code == 200
    assert await res.text() == 'STATUS OK'

    res = await client.get('/only-post')
    assert res.status_code == 404

    res = await client.post('/only-post')
    assert res.status_code == 200
    assert await res.text() == 'POST OK'

    res = await client.post('/42')
    assert res.status_code == 200
    assert await res.text() == 'Number 42'

    res = await client.post('/hello/john')
    assert res.status_code == 200
    assert await res.text() == 'Hello John'

    res = await client.post('/multiply/32/56')
    assert res.status_code == 200
    assert await res.text() == '1792'

# pylama: ignore=W
