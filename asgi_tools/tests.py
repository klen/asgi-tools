"""Testing tools."""

from __future__ import annotations

import asyncio
import binascii
import io
import mimetypes
import os
import random
from collections import deque
from contextlib import asynccontextmanager, suppress
from functools import partial
from http.cookies import SimpleCookie
from json import loads
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    Deque,
    Optional,
    Union,
    cast,
)
from urllib.parse import urlencode

from multidict import MultiDict
from yarl import URL

from ._compat import aio_cancel, aio_sleep, aio_spawn, aio_timeout, aio_wait
from .constants import BASE_ENCODING, DEFAULT_CHARSET
from .errors import ASGIConnectionClosedError, ASGIInvalidMessageError
from .response import Response, ResponseJSON, ResponseWebSocket, parse_websocket_msg
from .utils import CIMultiDict, parse_headers

if TYPE_CHECKING:
    from .types import TJSON, TASGIApp, TASGIMessage, TASGIReceive, TASGIScope, TASGISend


class TestResponse(Response):
    """Response for test client."""

    def __init__(self):
        super().__init__(b"")
        self.content = None

    async def __call__(self, _: TASGIScope, receive: TASGIReceive, send: TASGISend):  # noqa: ARG002
        self._receive = receive
        msg = await self._receive()
        assert msg.get("type") == "http.response.start", "Invalid Response"
        self.status_code = int(msg.get("status", 502))
        self.headers = cast(MultiDict, parse_headers(msg.get("headers", [])))
        self.content_type = self.headers.get("content-type")
        for cookie in self.headers.getall("set-cookie", []):
            self.cookies.load(cookie)

    async def stream(self) -> AsyncGenerator[bytes, None]:
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
        if self.content is None:
            body = b""
            async for chunk in self.stream():
                body += chunk
            self.content = body

        return self.content

    async def text(self) -> str:
        body = await self.body()
        return body.decode(DEFAULT_CHARSET)

    async def json(self) -> TJSON:
        text = await self.text()
        return loads(text)


class TestWebSocketResponse(ResponseWebSocket):
    """Support websockets in tests."""

    def connect(self) -> Coroutine[TASGIMessage, Any, Any]:
        return self.send({"type": "websocket.connect"})

    async def disconnect(self):
        await self.send({"type": "websocket.disconnect", "code": 1005})
        self.state = self.STATES.DISCONNECTED

    def send(self, msg, msg_type="websocket.receive"):
        """Send a message to a client."""
        return super().send(msg, msg_type=msg_type)

    async def receive(self, *, raw=False):
        """Receive messages from a client."""
        if self.partner_state == self.STATES.DISCONNECTED:
            raise ASGIConnectionClosedError

        msg = await self._receive()
        if not msg["type"].startswith("websocket."):
            raise ASGIInvalidMessageError(msg)

        if msg["type"] == "websocket.accept":
            self.partner_state = self.STATES.CONNECTED
            return await self.receive(raw=raw)

        if msg["type"] == "websocket.close":
            self.partner_state = self.STATES.DISCONNECTED
            raise ASGIConnectionClosedError

        return msg if raw else parse_websocket_msg(msg, charset=DEFAULT_CHARSET)


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

    def __init__(self, app: TASGIApp, base_url: str = "http://localhost"):
        self.app = app
        self.base_url = URL(base_url)
        self.cookies: SimpleCookie = SimpleCookie()
        self.headers: dict[str, str] = {}

    def __getattr__(self, name: str) -> Callable[..., Awaitable]:
        return partial(self.request, method=name.upper())

    async def request(
        self,
        path: str,
        method: str = "GET",
        *,
        query: Union[str, dict] = "",
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
        data: Union[bytes, str, dict, AsyncGenerator[Any, bytes]] = b"",
        json: TJSON = None,
        follow_redirect: bool = True,
        timeout: float = 10.0,
    ) -> TestResponse:
        """Make a HTTP requests."""

        headers = headers or dict(self.headers)

        if isinstance(data, str):
            data = Response.process_content(data)

        elif isinstance(data, dict):
            is_multipart = any(isinstance(value, io.IOBase) for value in data.values())
            if is_multipart:
                data, headers["Content-Type"] = encode_multipart(data)

            else:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = urlencode(data).encode(DEFAULT_CHARSET)

        elif json is not None:
            headers["Content-Type"] = "application/json"
            data = ResponseJSON.process_content(json)

        pipe = Pipe()

        if isinstance(data, bytes):
            headers.setdefault("Content-Length", str(len(data)))

        scope = self.build_scope(
            path,
            type="http",
            query=query,
            method=method,
            headers=headers,
            cookies=cookies,
        )

        async with aio_timeout(timeout):
            await aio_wait(
                pipe.stream(data),
                self.app(scope, pipe.receive_from_app, pipe.send_to_client),
            )

        res = TestResponse()
        await res(scope, pipe.receive_from_client, pipe.send_to_app)
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
        query: Union[str, dict, None] = None,
        headers: Optional[dict] = None,
        cookies: Optional[dict] = None,
    ):
        """Connect to a websocket."""
        pipe = Pipe()

        ci_headers = CIMultiDict(headers or {})

        scope = self.build_scope(
            path,
            headers=ci_headers,
            query=query,
            cookies=cookies,
            type="websocket",
            subprotocols=str(ci_headers.get("Sec-WebSocket-Protocol", "")).split(","),
        )
        ws = TestWebSocketResponse(scope, pipe.receive_from_client, pipe.send_to_app)
        async with aio_spawn(
            self.app,
            scope,
            pipe.receive_from_app,
            pipe.send_to_client,
        ):
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
        headers: Union[dict, CIMultiDict, None] = None,
        query: Union[str, dict, None] = None,
        cookies: Optional[dict] = None,
        **scope,
    ) -> TASGIScope:
        """Prepare a request scope."""
        headers = headers or {}
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

        # Setup client
        scope.setdefault("client", ("127.0.0.1", random.randint(1024, 65535)))  # noqa: S311

        return dict(
            {
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "path": url.path,
                "query_string": url.raw_query_string.encode(),
                "raw_path": url.raw_path.encode(),
                "root_path": "",
                "scheme": scope.get("type") == "http" and self.base_url.scheme or "ws",
                "headers": [
                    (key.lower().encode(BASE_ENCODING), str(val).encode(BASE_ENCODING))
                    for key, val in (headers or {}).items()
                ],
                "server": ("127.0.0.1", self.base_url.port),
            },
            **scope,
        )


def encode_multipart(data: dict) -> tuple[bytes, str]:
    body = io.BytesIO()
    boundary = binascii.hexlify(os.urandom(16))
    for name, data_value in data.items():
        value = data_value
        headers = f'Content-Disposition: form-data; name="{ name }"'
        if hasattr(value, "read"):
            filename = getattr(value, "name", None)
            if filename:
                headers = f'{ headers }; filename="{ Path(filename).name }"'
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
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


class Pipe:
    __slots__ = (
        "delay",
        "app_is_closed",
        "client_is_closed",
        "app_queue",
        "client_queue",
    )

    def __init__(self, delay: float = 1e-3):
        self.delay = delay
        self.app_is_closed = False
        self.client_is_closed = False
        self.app_queue: Deque[TASGIMessage] = deque()
        self.client_queue: Deque[TASGIMessage] = deque()

    async def send_to_client(self, msg: TASGIMessage):
        if self.client_is_closed:
            raise ASGIInvalidMessageError(msg.get("type"))

        if msg.get("type") == "websocket.close":
            self.client_is_closed = True

        elif msg.get("type") == "http.response.body":
            self.client_is_closed = not msg.get("more_body", False)

        self.client_queue.append(msg)

    async def send_to_app(self, msg: TASGIMessage):
        if self.app_is_closed:
            raise ASGIInvalidMessageError(msg.get("type"))

        if msg.get("type") == "http.disconnect":
            self.app_is_closed = True

        self.app_queue.append(msg)

    async def receive_from_client(self):
        while not self.client_queue:
            await aio_sleep(self.delay)
        return self.client_queue.popleft()

    async def receive_from_app(self):
        while not self.app_queue:
            await aio_sleep(self.delay)
        return self.app_queue.popleft()

    async def stream(self, data: Union[bytes, AsyncGenerator[Any, bytes]]):
        if isinstance(data, bytes):
            return await self.send_to_app(
                {"type": "http.request", "body": data, "more_body": False},
            )

        async for chunk in data:
            await self.send_to_app({"type": "http.request", "body": chunk, "more_body": True})
        await self.send_to_app({"type": "http.request", "body": b"", "more_body": False})
        return None


@asynccontextmanager
async def manage_lifespan(app, timeout: float = 3e-2):
    """Manage `Lifespan <https://asgi.readthedocs.io/en/latest/specs/lifespan.html>`_ protocol."""
    pipe = Pipe()

    scope = {"type": "lifespan"}

    async def safe_spawn():
        with suppress(BaseException):
            await app(scope, pipe.receive_from_app, pipe.send_to_client)

    async with aio_spawn(safe_spawn) as task:
        await pipe.send_to_app({"type": "lifespan.startup"})

        with suppress(TimeoutError, asyncio.TimeoutError):  # python 39, 310
            async with aio_timeout(timeout):
                msg = await pipe.receive_from_client()
                if msg["type"] == "lifespan.startup.failed":
                    await aio_cancel(task)

        yield

        await pipe.send_to_app({"type": "lifespan.shutdown"})
        with suppress(TimeoutError, asyncio.TimeoutError):  # python 39, 310
            async with aio_timeout(timeout):
                await pipe.receive_from_client()
