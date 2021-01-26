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
            "query": dict(request.query),

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
    assert data['url'] == 'http://localhost:80/test?var=42'
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
