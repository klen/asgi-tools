"""Testing tools."""

import binascii
import io
import mimetypes
import os
import typing as t
from collections import deque
from contextlib import asynccontextmanager
from functools import partial
from http.cookies import SimpleCookie
from json import dumps, loads
from pathlib import Path
from urllib.parse import urlencode

from yarl import URL

from asgi_tools import ASGIConnectionClosed
from asgi_tools._compat import FIRST_COMPLETED, aio_cancel, aio_sleep, aio_spawn, aio_wait
from asgi_tools.response import Response, ResponseWebSocket, parse_websocket_msg
from asgi_tools.typing import ASGIApp, JSONType, Message, Receive, Scope, Send
from asgi_tools.utils import CIMultiDict, parse_headers, to_awaitable


class TestResponse(Response):
    """Response for test client."""

    async def __call__(self, _: Scope, receive: Receive, __: Send):  # type: ignore
        self._receive = receive
        msg = await self._receive()
        assert msg.get("type") == "http.response.start", "Invalid Response"
        self.status_code = int(msg.get("status", 502))
        self.headers = parse_headers(msg.get("headers", []))  # type: ignore
        self.content_type = self.headers.get("content-type")
        for cookie in self.headers.getall("set-cookie", []):
            self.cookies.load(cookie)

    async def stream(self) -> t.AsyncGenerator[bytes, None]:
        """Stream the response."""
        more_body = True
        while more_body:
            msg = await self._receive()
            if msg.get("type") == "http.response.body":
                chunk = msg.get("body")
                if chunk:
                    yield chunk
                more_body = msg.get("more_body", False)

    async def body(self) -> bytes:
        """Load response body."""
        body_ = b""
        async for chunk in self.stream():
            body_ += chunk
        return body_

    async def text(self) -> str:
        body = await self.body()
        return body.decode(self.charset)

    async def json(self) -> JSONType:
        text = await self.text()
        return loads(text)


class TestWebSocketResponse(ResponseWebSocket):
    """Support websockets in tests."""

    # Disable app methods for clients
    accept = close = None  # type: ignore

    def connect(self) -> t.Coroutine[Message, t.Any, t.Any]:
        return self.send({"type": "websocket.connect"})

    async def disconnect(self):
        await self.send({"type": "websocket.disconnect", "code": 1005})
        self.state = self.STATES.DISCONNECTED

    def send(self, msg, type="websocket.receive"):  # noqa
        """Send a message to a client."""
        return super().send(msg, type=type)

    async def receive(self, raw=False):
        """Receive messages from a client."""
        if self.partner_state == self.STATES.DISCONNECTED:
            raise ASGIConnectionClosed

        msg = await self._receive()
        if not msg["type"].startswith("websocket."):
            raise ValueError(f"Invalid websocket message: {msg!r}")

        if msg["type"] == "websocket.accept":
            self.partner_state = self.STATES.CONNECTED
            return await self.receive(raw=raw)

        if msg["type"] == "websocket.close":
            self.partner_state = self.STATES.DISCONNECTED
            raise ASGIConnectionClosed("Connection has been closed.")

        return msg if raw else parse_websocket_msg(msg, charset=self.charset)


class ASGITestClient:
    """The test client allows you to make requests against an ASGI application.

    Features:

    * cookies
    * multipart/form-data
    * follow redirects
    * request streams
    * response streams
    * websocket support
    * lifespan management

    """

    def __init__(self, app: ASGIApp, base_url: str = "http://localhost"):
        self.app = app
        self.base_url = URL(base_url)
        self.cookies: SimpleCookie = SimpleCookie()
        self.headers: t.Dict[str, str] = {}

    def __getattr__(self, name: str) -> t.Callable[..., t.Awaitable]:
        return partial(self.request, method=name.upper())

    async def request(
        self,
        path: str,
        method: str = "GET",
        query: t.Union[str, t.Dict] = "",
        headers: t.Dict[str, str] = None,
        cookies: t.Dict = None,
        data: t.Union[bytes, str, t.Dict, t.AsyncGenerator] = b"",
        json: JSONType = None,
        follow_redirect: bool = True,
        timeout: float = 10.0,
    ) -> TestResponse:
        """Make a HTTP requests."""

        res = TestResponse()
        headers = headers or dict(self.headers)

        if isinstance(data, str):
            data = data.encode(res.charset)

        elif isinstance(data, dict):
            is_multipart = any(isinstance(value, io.IOBase) for value in data.values())
            if is_multipart:
                data, headers["Content-Type"] = encode_multipart(data)

            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = urlencode(data).encode(res.charset)

        elif json is not None:
            headers["Content-Type"] = "application/json"
            data = dumps(json).encode(res.charset)

        receive_from_client, send_to_app = simple_stream()
        receive_from_app, send_to_client = simple_stream()

        if isinstance(data, bytes):
            headers.setdefault("Content-Length", str(len(data)))

        scope = self.build_scope(
            path,
            headers=headers,
            query=query,
            cookies=cookies,
            type="http",
            method=method,
        )

        await aio_wait(
            aio_wait(
                self.app(scope, receive_from_client, send_to_client),
                stream_data(data, send_to_app),
            ),
            raise_timeout(timeout),
            strategy=FIRST_COMPLETED,
        )
        await send_to_client({"type": "http.response.body", "more_body": False})
        await res(scope, receive_from_app, send_to_app)
        for n, v in res.cookies.items():
            self.cookies[n] = v

        if follow_redirect and res.status_code in {301, 302, 303, 307, 308}:
            return await self.get(res.headers["location"])

        return res

    # TODO: Timeouts for websockets
    @asynccontextmanager
    async def websocket(
        self,
        path: str,
        query: t.Union[str, t.Dict] = None,
        headers: t.Dict = None,
        cookies: t.Dict = None,
    ):
        """Connect to a websocket."""
        receive_from_client, send_to_app = simple_stream()
        receive_from_app, send_to_client = simple_stream()

        ci_headers = CIMultiDict(headers or {})

        scope = self.build_scope(
            path,
            headers=ci_headers,
            query=query,
            cookies=cookies,
            type="websocket",
            subprotocols=str(ci_headers.get("Sec-WebSocket-Protocol", "")).split(","),
        )
        ws = TestWebSocketResponse(scope, receive_from_app, send_to_app)
        async with aio_spawn(self.app, scope, receive_from_client, send_to_client):
            await ws.connect()
            yield ws
            await ws.disconnect()

    def lifespan(self, timeout: float = 3e-2):
        """Manage `Lifespan <https://asgi.readthedocs.io/en/latest/specs/lifespan.html>`_
        protocol."""
        return manage_lifespan(self.app, timeout=timeout)

    def build_scope(
        self,
        path: str,
        headers: t.Union[t.Dict, CIMultiDict] = None,
        query: t.Union[str, t.Dict] = None,
        cookies: t.Dict = None,
        **scope,
    ) -> Scope:
        """Prepare a request scope."""
        headers = headers or {}
        headers.setdefault("Remote-Addr", "127.0.0.1")
        headers.setdefault("User-Agent", "ASGI-Tools-Test-Client")
        headers.setdefault("Host", self.base_url.host)

        if cookies:
            for c, v in cookies.items():
                self.cookies[c] = v

        if len(self.cookies):
            headers.setdefault("Cookie", self.cookies.output(header="", sep=";"))

        url = URL(path)
        if query:
            url = url.with_query(query)

        return dict(
            {
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "path": url.path,
                "query_string": url.query_string.encode("latin-1"),
                "raw_path": url.raw_path.encode("latin-1"),
                "root_path": "",
                "scheme": scope.get("type") == "http" and self.base_url.scheme or "ws",
                "headers": [
                    (key.lower().encode("latin-1"), str(val).encode("latin-1"))
                    for key, val in (headers or {}).items()
                ],
                "server": ("127.0.0.1", self.base_url.port),
            },
            **scope,
        )


def encode_multipart(data: t.Dict) -> t.Tuple[bytes, str]:
    body = io.BytesIO()
    boundary = binascii.hexlify(os.urandom(16))
    for name, value in data.items():
        headers = f'Content-Disposition: form-data; name="{ name }"'
        if hasattr(value, "read"):
            filename = getattr(value, "name", None)
            if filename:
                headers = f'{ headers }; filename="{ Path(filename).name }"'
                content_type = (
                    mimetypes.guess_type(filename)[0] or "application/octet-stream"
                )
                headers = f"{ headers }\r\nContent-Type: { content_type }"
            value = value.read()

        body.write(b"--%b\r\n" % boundary)
        body.write(headers.encode("utf-8"))
        body.write(b"\r\n\r\n")
        if isinstance(value, str):
            value = value.encode("utf-8")
        body.write(value)
        body.write(b"\r\n")

    body.write(b"--%b--\r\n" % boundary)
    return body.getvalue(), (b"multipart/form-data; boundary=%s" % boundary).decode()


def simple_stream(maxlen=None):
    queue = deque(maxlen=maxlen)

    async def receive():
        while not queue:
            await aio_sleep(1e-3)
        return queue.popleft()

    return receive, to_awaitable(queue.append)


async def raise_timeout(timeout: t.Union[int, float]):
    await aio_sleep(timeout)
    raise TimeoutError("Timeout occured")


async def stream_data(
    data: t.Union[bytes, t.AsyncGenerator[t.Any, bytes]],
    send: t.Callable[..., t.Awaitable],
):
    """Stream a data to an application."""

    if isinstance(data, bytes):
        return await send({"type": "http.request", "body": data, "more_body": False})

    async for chunk in data:
        await send({"type": "http.request", "body": chunk, "more_body": True})
    await send({"type": "http.request", "body": b"", "more_body": False})


@asynccontextmanager
async def manage_lifespan(app, timeout: float = 3e-2):
    """Manage `Lifespan <https://asgi.readthedocs.io/en/latest/specs/lifespan.html>`_ protocol."""
    receive_from_client, send_to_app = simple_stream()
    receive_from_app, send_to_client = simple_stream()

    async def safe_spawn():
        try:
            await app({"type": "lifespan"}, receive_from_client, send_to_client)
        except BaseException:  # noqa
            pass

    async with aio_spawn(safe_spawn) as task:
        await send_to_app({"type": "lifespan.startup"})
        msg = await aio_wait(
            receive_from_app(), aio_sleep(timeout), strategy=FIRST_COMPLETED
        )
        if msg and isinstance(msg, t.Mapping):
            if msg["type"] == "lifespan.startup.failed":
                await aio_cancel(task)
            else:
                assert msg["type"] == "lifespan.startup.complete"

        yield

        await send_to_app({"type": "lifespan.shutdown"})
        msg = await aio_wait(
            receive_from_app(), aio_sleep(timeout), strategy=FIRST_COMPLETED
        )
        if msg and isinstance(msg, t.Mapping):
            assert msg["type"] == "lifespan.shutdown.complete"


# pylama:ignore=D
