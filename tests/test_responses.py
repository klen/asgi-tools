"""ASGI Tools Responses Tests."""

import pytest


async def test_response():
    from asgi_tools import Response

    response = Response("Content", content_type='text/html')
    response.cookies['session'] = 'test-session'
    response.cookies['session']['path'] = '/'
    response.cookies['lang'] = 'en'
    assert response.status_code == 200
    assert await response.body() == b"Content"
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

    response = parse_response({'test': 'passed'})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    _, body = [m async for m in response]
    assert body == {
        'body': b'{"test": "passed"}', 'type': 'http.response.body', 'more_body': False}

    response = parse_response((500, 'SERVER ERROR'))
    assert response.status_code == 500
    assert response.content == 'SERVER ERROR'

    response = parse_response((302, {'location': 'https://google.com'}, 'go away'))
    assert response.status_code == 302
    assert response.content == 'go away'
    assert response.headers['location'] == 'https://google.com'

    with pytest.raises(AssertionError):
        parse_response((None, 'SERVER ERROR'))


async def test_html_response():
    from asgi_tools import ResponseHTML

    response = ResponseHTML("Content")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert await response.body() == b"Content"


async def test_text_response():
    from asgi_tools import ResponseText

    response = ResponseText("Content")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'text/plain; charset=utf-8'
    assert await response.body() == b"Content"


async def test_json_response():
    from asgi_tools import ResponseJSON

    response = ResponseJSON([1, 2, 3])
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    assert await response.body() == b"[1, 2, 3]"


async def test_redirect_response():
    from asgi_tools import ResponseRedirect

    response = ResponseRedirect('/logout')
    assert response.status_code == 307
    assert response.headers['location'] == '/logout'
    assert await response.body() == b""


async def test_error_response():
    from asgi_tools import ResponseError

    response = ResponseError(status_code=503)
    assert response.content == "The server cannot process the request due to a high load"

    response = ResponseError.NOT_FOUND()
    assert response.status_code == 404
    assert response.content == "Nothing matches the given URI"

    response = ResponseError.INTERNAL_SERVER_ERROR('custom message')
    assert response.status_code == 500
    assert response.content == "custom message"


# TODO: Exceptions
async def test_stream_response(anyio_backend, Client):
    from asgi_tools import ResponseStream
    from asgi_tools._compat import aio_sleep

    async def filler(timeout=.001):
        for idx in range(10):
            await aio_sleep(timeout)
            yield idx

    response = ResponseStream(filler())
    messages = []
    async for msg in response:
        messages.append(msg)

    assert len(messages) == 12
    assert messages[-2] == {'body': b'9', 'more_body': True, 'type': 'http.response.body'}
    assert messages[-1] == {'body': b'', 'more_body': False, 'type': 'http.response.body'}

    def app(scope, receive, send):
        response = ResponseStream(filler())
        return response(scope, receive, send)

    client = Client(app)
    res = await client.get('/')
    assert res.status_code == 200
    assert await res.text() == '0123456789'


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
    from asgi_tools.tests import simple_stream

    app_receive, send_to_app = simple_stream()
    client_receive, send_to_client = simple_stream()

    ws = ResponseWebSocket({}, app_receive, send_to_client)
    await send_to_app({'type': 'websocket.connect'})
    await ws.accept()
    msg = await client_receive()
    assert msg == {'type': 'websocket.accept'}
    await send_to_app({'type': 'websocket.disconnect'})
    msg = await ws.receive()
    assert msg == {'type': 'websocket.disconnect'}
    assert not ws.connected

    async def app(scope, receive, send):
        async with ResponseWebSocket(scope, receive, send) as ws:
            await ws.accept()
            msg = await ws.receive()
            assert msg == 'ping'
            await ws.send('pong')

    async with Client(app).websocket('/') as ws:
        await ws.send('ping')
        msg = await ws.receive()
        assert msg == 'pong'
        with pytest.raises(ASGIConnectionClosed):
            await ws.receive()
