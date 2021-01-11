"""Test Request."""


async def test_request():
    from asgi_tools import Request

    # Request is lazy
    request = Request([], None)
    assert request is not None

    scope = {
        'type': 'http',
        'asgi': {'version': '3.0'},
        'http_version': '1.1',
        'method': 'GET',
        'headers': [
            (b'host', b'testserver:8000'),
            (b'accept', b'*/*'),
            (b'accept-encoding', b'gzip, deflate'),
            (b'connection', b'keep-alive'),
            (b'content-type', b'application/x-www-form-urlencoded'),
            (b'user-agent', b'python-httpx/0.16.1'),
            (b'test-header', b'test-value'),
            (b'cookie', b'session=test-session'),
        ],
        'scheme': 'http',
        'path': '/testurl',
        'query_string': b'a=1%202',
        'server': ('testserver', 8000),
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
    assert request.query['a'] == '1 2'
    assert request.type == 'http'
    assert request['type'] == 'http'
    assert str(request.url) == 'http://testserver:8000/testurl?a=1%202'

    body = await request.body()
    assert body

    formdata = await request.form()
    assert formdata
    assert formdata['name'] == 'value'

    formdata2 = await request.form()
    assert formdata2 == formdata

    data = await request.data()
    assert data == formdata


async def test_multipart(client):
    from asgi_tools import Request, ResponseHTML

    async def app(scope, receive, send):
        request = Request(scope, receive)
        data = await request.form()
        response = ResponseHTML(
            data['test'].split(b'\n')[0]
        )
        return await response(scope, receive, send)

    async with client(app) as req:
        res = await req.post('/', files={'test': open(__file__)})
        assert res.status_code == 200
        assert res.text == '"""Test Request."""'
        assert res.headers['content-length'] == str(len(res.text))
