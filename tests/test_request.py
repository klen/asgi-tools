"""Test Request."""

import pytest
from copy import copy


async def test_request():
    from asgi_tools import Request

    # Request is lazy
    request = Request({}, None)
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
        return {'body': b'name=test%20passed'}

    request = Request(scope, receive)
    assert request.method == 'GET'
    assert request.headers
    assert request.headers['User-Agent'] == 'python-httpx/0.16.1'
    assert request.url
    assert str(request.url) == 'http://testserver:8000/testurl?a=1%202'
    assert request.client == ('127.0.0.1', 123)
    assert request.cookies
    assert request.cookies['session'] == 'test-session'
    assert request.http_version == '1.1'
    assert request.type == 'http'
    assert request['type'] == 'http'

    formdata = await request.form()
    assert formdata
    assert formdata['name'] == 'test passed'

    with pytest.raises(RuntimeError):
        body = await request.body()
        assert body

    r2 = copy(request)
    assert r2 is not request


async def test_multipart(Client):
    from asgi_tools import Request, ResponseHTML

    async def app(scope, receive, send):
        request = Request(scope, receive)
        data = await request.form()
        response = ResponseHTML(
            data['test'].read().decode().split('\n')[0]
        )
        return await response(scope, receive, send)

    client = Client(app)
    res = await client.post('/', data={'test': open(__file__)})
    assert res.status_code == 200
    assert await res.text() == '"""Test Request."""'
    assert res.headers['content-length'] == str(len('"""Test Request."""'))


async def test_json(GenRequest):
    from asgi_tools import ASGIError

    req = GenRequest(body=[b'invalid'])
    try:
        await req.json()
    except ASGIError as exc:
        assert exc.args[0] == 'Invalid JSON'

    req = GenRequest(body=[b'{"test": 42}'])
    json = await req.json()
    assert json == {'test': 42}


async def test_data(Client):
    from asgi_tools import ResponseMiddleware, Request

    async def app(scope, receive, send):
        request = Request(scope, receive)
        data = await request.data()
        return isinstance(data, str) and data or dict(data)

    app = ResponseMiddleware(app)
    client = Client(app)

    # Post formdata
    res = await client.post('/', data={'test': 'passed'})
    assert res.status_code == 200
    assert await res.json() == {'test': 'passed'}

    # Post json
    res = await client.post('/', json={'test': 'passed'})
    assert res.status_code == 200
    assert await res.json() == {'test': 'passed'}

    # Post other
    res = await client.post('/', data='test passed')
    assert res.status_code == 200
    assert await res.text() == 'test passed'
