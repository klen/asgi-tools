"""ASGI Tools Responses Tests."""
from __future__ import annotations

from http import cookies
from typing import TYPE_CHECKING, List

import pytest

if TYPE_CHECKING:
    from asgi_tools.types import TASGIMessage


async def test_response():
    from asgi_tools import Response

    response = Response("Content", content_type="text/html", cookies={"lang": "en"})
    response.cookies["session"] = "test-session"
    response.cookies["session"]["path"] = "/"
    assert response.status_code == 200
    assert response.content == b"Content"

    messages = await read_response(response)
    assert messages
    assert messages[0] == {
        "headers": [
            (b"content-type", b"text/html; charset=utf-8"),
            (b"content-length", b"7"),
            (b"set-cookie", b"lang=en"),
            (b"set-cookie", b"session=test-session; Path=/"),
        ],
        "status": 200,
        "type": "http.response.start",
    }
    assert messages[1] == {"body": b"Content", "type": "http.response.body"}

    response = Response(b"image", content_type="image/png")
    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"image/png"), (b"content-length", b"5")],
        },
        {"type": "http.response.body", "body": b"image"},
    ]


async def test_html_response():
    from asgi_tools import ResponseHTML

    response = ResponseHTML("Content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.content == b"Content"

    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"content-length", b"7"),
            ],
        },
        {"type": "http.response.body", "body": b"Content"},
    ]


async def test_text_response():
    from asgi_tools import ResponseText

    response = ResponseText("Content")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.content == b"Content"

    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", b"7"),
            ],
        },
        {"type": "http.response.body", "body": b"Content"},
    ]


async def test_json_response():
    from asgi_tools import ResponseJSON

    response = ResponseJSON([1, 2, 3])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.content == b"[1,2,3]"

    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", b"7"),
            ],
        },
        {"type": "http.response.body", "body": b"[1,2,3]"},
    ]

    response = ResponseJSON(None)
    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", b"4"),
            ],
        },
        {"type": "http.response.body", "body": b"null"},
    ]


async def test_redirect_response():
    from asgi_tools import ResponseRedirect

    response = ResponseRedirect("/logout")
    assert response.status_code == 307
    assert response.headers["location"] == "/logout"
    assert response.content == b""
    messages = await read_response(response)
    assert messages == [
        {
            "type": "http.response.start",
            "status": 307,
            "headers": [(b"location", b"/logout"), (b"content-length", b"0")],
        },
        {"type": "http.response.body", "body": b""},
    ]


async def test_error_response():
    from asgi_tools import ResponseError

    response = ResponseError(status_code=503)
    assert response.content == b"The server cannot process the request due to a high load"

    response = ResponseError.NOT_FOUND()
    assert response.status_code == 404
    assert response.content == b"Nothing matches the given URI"

    response = ResponseError.INTERNAL_SERVER_ERROR("custom message")
    assert response.status_code == 500
    assert response.content == b"custom message"


# TODO: Exceptions
async def test_stream_response(client_cls):
    from asgi_tools import ResponseStream
    from asgi_tools._compat import aio_sleep

    async def filler(timeout=0.001):
        for idx in range(10):
            await aio_sleep(timeout)
            yield idx

    response = ResponseStream(filler())
    messages = await read_response(response)
    assert len(messages) == 12
    assert messages[-2] == {
        "body": b"9",
        "more_body": True,
        "type": "http.response.body",
    }
    assert messages[-1] == {"body": b"", "type": "http.response.body"}

    def app(scope, receive, send):
        response = ResponseStream(filler())
        return response(scope, receive, send)

    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "0123456789"


async def test_file_response():
    from asgi_tools import ASGIError, ResponseFile

    response = ResponseFile(__file__)
    assert response.headers["content-length"]
    assert response.headers["content-type"] == "text/x-python"
    assert response.headers["last-modified"]
    assert response.headers["etag"]
    assert "content-disposition" not in response.headers

    response = ResponseFile(__file__, filename="tests.py")
    assert response.headers["content-disposition"] == 'attachment; filename="tests.py"'

    messages = await read_response(response)
    assert len(messages) >= 3
    assert b"ASGI Tools Responses Tests" in messages[1]["body"]

    response = ResponseFile(__file__, headers_only=True)
    messages = await read_response(response)
    assert len(messages) == 3
    assert messages[1] == {
        "type": "http.response.body",
        "body": b"",
        "more_body": True,
    }

    with pytest.raises(ASGIError):
        response = ResponseFile("unknown")


async def test_sse_response(client_cls):
    from asgi_tools import ResponseSSE
    from asgi_tools._compat import aio_sleep

    async def filler(timeout=0.001):
        for _idx in range(2):
            await aio_sleep(timeout)
            yield "data: test"
            yield {"event": "ping"}

    response = ResponseSSE(filler())
    messages = await read_response(response)
    assert messages[1]["body"] == b"data: test\n\n"
    assert messages[2]["body"] == b"event: ping\n\n"

    def app(scope, receive, send):
        response = ResponseSSE(filler())
        return response(scope, receive, send)

    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 200
    text = await res.text()
    assert "data: test\n\n" in text
    assert "event: ping\n\n" in text


async def test_websocket_response(client_cls):
    import json

    from asgi_tools import ASGIConnectionClosedError, ResponseWebSocket
    from asgi_tools.tests import Pipe

    pipe = Pipe()

    ws = ResponseWebSocket({}, pipe.receive_from_app, pipe.send_to_client)
    await pipe.send_to_app({"type": "websocket.connect"})
    await ws.accept()
    msg = await pipe.receive_from_client()
    assert msg == {"type": "websocket.accept"}
    await pipe.send_to_app({"type": "websocket.disconnect"})
    msg = await ws.receive()
    assert msg == {"type": "websocket.disconnect"}
    assert not ws.connected

    async def app(scope, receive, send):
        async with ResponseWebSocket(scope, receive, send) as ws:
            await ws.accept()
            msg = await ws.receive()
            assert msg == "ping"
            await ws.send("pong")
            await ws.send_json(["ping", "pong"])

    async with client_cls(app).websocket("/") as ws:
        await ws.send("ping")
        msg = await ws.receive()
        assert msg == "pong"
        msg = json.loads(await ws.receive())
        assert msg == ["ping", "pong"]
        with pytest.raises(ASGIConnectionClosedError):
            await ws.receive()


async def test_parse_response():
    from asgi_tools import parse_response

    response = parse_response({"test": "passed"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    _, body = await read_response(response)
    assert body == {"body": b'{"test":"passed"}', "type": "http.response.body"}

    response = parse_response((500, "SERVER ERROR"))
    assert response.status_code == 500
    assert response.content == b"SERVER ERROR"

    response = parse_response((302, {"location": "https://google.com"}, "go away"))
    assert response.status_code == 302
    assert response.content == b"go away"
    assert response.headers["location"] == "https://google.com"

    with pytest.raises(AssertionError):
        parse_response((None, "SERVER ERROR"))


async def read_response(response) -> List[TASGIMessage]:
    from functools import partial

    from asgi_tools._compat import aio_sleep
    from asgi_tools.utils import to_awaitable

    messages = []
    await response(None, partial(aio_sleep, 10), to_awaitable(messages.append))
    return messages


# ruff: noqa: N803
