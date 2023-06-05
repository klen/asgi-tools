"""Test Request."""
from __future__ import annotations

from copy import copy
from pathlib import Path

import pytest


async def test_base(receive, send):
    from asgi_tools import Request

    # Request is lazy
    request = Request({}, receive, send)
    assert request is not None

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "headers": [
            (b"host", b"testserver:8000"),
            (b"accept", b"*/*"),
            (b"accept-encoding", b"gzip, deflate"),
            (b"connection", b"keep-alive"),
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"user-agent", b"python-httpx/0.16.1"),
            (b"test-header", b"test-value"),
            (b"cookie", b"session=test-session"),
        ],
        "scheme": "http",
        "path": "/testurl",
        "query_string": b"a=1%202",
        "server": ("testserver", 8000),
        "client": ("127.0.0.1", 123),
        "root_path": "",
    }

    async def receive2():
        return {"body": b"name=test%20passed"}

    request = Request(scope, receive2, send)
    assert request.method == "GET"
    assert request.headers
    assert request.headers["User-Agent"] == "python-httpx/0.16.1"
    assert request.url
    assert str(request.url) == "http://testserver:8000/testurl?a=1%202"
    assert request.client == ("127.0.0.1", 123)
    assert request.cookies
    assert request.cookies["session"] == "test-session"
    assert request.http_version == "1.1"
    assert request.type == "http"
    assert request["type"] == "http"

    formdata = await request.form()
    assert formdata
    assert formdata["name"] == "test passed"

    with pytest.raises(RuntimeError):
        assert await request.body()

    r2 = copy(request)
    assert r2 is not request


async def test_media(gen_request):
    req = gen_request()
    assert req.media
    assert not req.content_type

    req = gen_request(headers={"content-type": "text/html; charset=iso-8859-1"})
    assert req.media
    assert req.media["charset"]
    assert req.media["content_type"]
    assert req.content_type == "text/html"


async def test_body(gen_request):
    req = gen_request(body=[b"any"])
    body = await req.body()
    assert body == b"any"

    body = await req.body()
    assert body == b"any"


async def test_json(gen_request):
    from asgi_tools.errors import ASGIDecodeError

    req = gen_request(body=[b"invalid"])
    with pytest.raises(ASGIDecodeError):
        await req.json()

    req = gen_request(body=[b'{"test": 42}'])
    json = await req.json()
    assert json == {"test": 42}


async def test_data(client_cls, gen_request):
    from asgi_tools import Request, ResponseMiddleware

    async def simple_app(scope, receive, send):
        request = Request(scope, receive, send)
        data = await request.data()
        return isinstance(data, (str, bytes)) and data or dict(data)  # type: ignore[]

    app = ResponseMiddleware(simple_app)
    client = client_cls(app)

    # Post formdata
    res = await client.post("/", data={"test": "passed"})
    assert res.status_code == 200
    assert await res.json() == {"test": "passed"}

    # Post json
    res = await client.post("/", json={"test": "passed"})
    assert res.status_code == 200
    assert await res.json() == {"test": "passed"}

    # Post other
    res = await client.post("/", data="test passed")
    assert res.status_code == 200
    assert await res.text() == "test passed"

    # Invalid data
    res = await client.post(
        "/",
        data="invalid",
        headers={"content-type": "application/json"},
    )
    assert res.status_code == 200
    assert await res.text() == "invalid"

    req = gen_request(body=[b"invalid"], headers={"content-type": "application/json"})
    assert await req.data() == b"invalid"

    from asgi_tools.errors import ASGIDecodeError

    with pytest.raises(ASGIDecodeError):
        await req.data(raise_errors=True)


async def test_multipart(client_cls):
    from asgi_tools import Request, ResponseHTML

    async def app(scope, receive, send):
        request = Request(scope, receive, send)
        data = await request.form()
        response = ResponseHTML(data["test"].read().decode().split("\n")[0])
        return await response(scope, receive, send)

    client = client_cls(app)
    with Path(__file__).open() as f:
        res = await client.post("/", data={"test": f})
    assert res.status_code == 200
    assert await res.text() == '"""Test Request."""'
    assert res.headers["content-length"] == str(len('"""Test Request."""'))


async def test_multipart_max_size(client_cls):
    from asgi_tools import Request, ResponseHTML

    async def app(scope, receive, send):
        request = Request(scope, receive, send)
        data = await request.form(max_size=100)
        if data:
            response = ResponseHTML(data["test"].read().decode().split("\n")[0])
        else:
            response = ResponseHTML("No data")
        return await response(scope, receive, send)

    client = client_cls(app)
    with Path(__file__).open() as f:
        res = await client.post("/", data={"test": f})
    assert res.status_code == 200
    body = await res.text()
    assert await res.text() == "No data"
    assert res.headers["content-length"] == str(len("No data"))


# ruff: noqa: N803
