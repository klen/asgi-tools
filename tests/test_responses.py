"""ASGI Tools Responses Tests."""

import pytest


async def test_response():
    from asgi_tools import Response

    response = Response("Content", content_type='text/html')
    response.cookies['session'] = 'test-session'
    response.cookies['session']['path'] = '/'
    response.cookies['lang'] = 'en'
    assert response.body == b"Content"
    assert response.status_code == 200
    messages = [m async for m in response]
    assert messages
    assert messages[0] == {
        'headers': [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'content-length', b'7'),
            (b'set-cookie', b'session=test-session; Path=/'),
            (b'set-cookie', b'lang=en'),
        ],
        'status': 200,
        'type': 'http.response.start'
    }
    assert messages[1] == {'body': b'Content', 'type': 'http.response.body', 'more_body': False}


async def test_parse_response():
    from asgi_tools import parse_response

    response = await parse_response({'test': 'passed'})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    _, body = [m async for m in response]
    assert body == {
        'body': b'{"test": "passed"}', 'type': 'http.response.body', 'more_body': False}

    response = await parse_response((500, 'SERVER ERROR'))
    assert response.status_code == 500
    assert response.content == 'SERVER ERROR'

    response = await parse_response((302, {'location': 'https://google.com'}, 'go away'))
    assert response.status_code == 302
    assert response.content == 'go away'
    assert response.headers['location'] == 'https://google.com'


async def test_html_response():
    from asgi_tools import ResponseHTML

    response = ResponseHTML("Content")
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html; charset=utf-8'


async def test_text_response():
    from asgi_tools import ResponseText

    response = ResponseText("Content")
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/plain; charset=utf-8'


async def test_json_response():
    from asgi_tools import ResponseJSON

    response = ResponseJSON([1, 2, 3])
    assert response.body == b"[1, 2, 3]"
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'


async def test_redirect_response():
    from asgi_tools import ResponseRedirect

    response = ResponseRedirect('/logout')
    assert response.body == b""
    assert response.status_code == 307
    assert response.headers['location'] == '/logout'


async def test_error_response():
    from asgi_tools import ResponseError

    response = ResponseError(503)
    assert response.content == "The server cannot process the request due to a high load"


async def test_stream_response(anyio_backend, Client):
    import anyio as aio
    from asgi_tools import ResponseStream

    async def fill(timeout=.001):
        for idx in range(10):
            await aio.sleep(timeout)
            yield idx

    response = ResponseStream(fill())
    messages = []
    async for msg in response:
        messages.append(msg)

    assert len(messages) == 12
    assert messages[-2] == {'body': b'9', 'more_body': True, 'type': 'http.response.body'}
    assert messages[-1] == {'body': b'', 'more_body': False, 'type': 'http.response.body'}

    def app(scope, receive, send):
        response = ResponseStream(fill())
        return response(scope, receive, send)

    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 200
    assert res.text == '0123456789'


async def test_file_response(anyio_backend):
    from asgi_tools import ResponseFile, ASGIError

    response = ResponseFile(__file__)
    assert response.headers['content-length']
    assert response.headers['content-type'] == 'text/x-python'
    assert response.headers['last-modified']
    assert response.headers['etag']
    assert response.headers['content-disposition'] == 'attachment; filename="test_responses.py"'

    messages = []
    async for msg in response:
        messages.append(msg)

    assert len(messages) >= 3
    assert b"ASGI Tools Responses Tests" in messages[1]['body']

    response = ResponseFile(__file__, headers_only=True)

    messages = []
    async for msg in response:
        messages.append(msg)

    assert len(messages) == 2

    with pytest.raises(ASGIError):
        response = ResponseFile('unknown')


async def test_websocket_response(anyio_backend, Client):
    from asgi_tools import ResponseWebSocket, ASGIConnectionClosed

    async def app(scope, receive, send):
        ws = ResponseWebSocket(scope, receive, send)
        await ws.accept()
        msg = await ws.receive()
        assert msg == 'ping'
        await ws.send('pong')
        await ws.close()

    async with Client(app).websocket('/') as ws:
        await ws.send('ping')
        msg = await ws.receive()
        assert msg == 'pong'
        with pytest.raises(ASGIConnectionClosed):
            await ws.receive()
