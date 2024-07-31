"""ASGI responses."""

from __future__ import annotations

from email.utils import formatdate
from enum import Enum
from functools import partial
from hashlib import md5
from http import HTTPStatus
from http.cookies import SimpleCookie
from mimetypes import guess_type
from pathlib import Path
from stat import S_ISDIR
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Mapping, Optional, Union
from urllib.parse import quote, quote_plus

from multidict import MultiDict

from ._compat import FIRST_COMPLETED, aio_stream_file, aio_wait, json_dumps
from .constants import BASE_ENCODING, DEFAULT_CHARSET
from .errors import ASGIConnectionClosedError, ASGIError
from .request import Request

if TYPE_CHECKING:
    from .types import TASGIMessage, TASGIReceive, TASGIScope, TASGISend


class Response:
    """A base class to make ASGI_ responses.

    :param content: A response's body
    :type content: str | bytes
    :param status_code: An HTTP status code
    :type status_code: int
    :param headers: A dictionary of HTTP headers
    :type headers: dict[str, str]
    :param content_type: A string with the content-type
    :type content_type: str
    :param cookies: An initial dictionary of cookies
    :type cookies: dict[str, str]
    """

    headers: MultiDict  #: Multidict of response's headers
    cookies: SimpleCookie
    """ Set/Update cookies

    * `response.cookies[name] = value` ``str`` -- set a cookie's value
    * `response.cookies[name]['path'] = value` ``str`` -- set a cookie's path
    * `response.cookies[name]['expires'] = value` ``int`` -- set a cookie's expire
    * `response.cookies[name]['domain'] = value` ``str`` -- set a cookie's domain
    * `response.cookies[name]['max-age'] = value` ``int`` -- set a cookie's max-age
    * `response.cookies[name]['secure'] = value` ``bool``-- is the cookie
      should only be sent if request is SSL
    * `response.cookies[name]['httponly'] = value` ``bool`` -- is the cookie
      should be available through HTTP request only (not from JS)
    * `response.cookies[name]['samesite'] = value` ``str`` -- set a cookie's
      strategy ('lax'|'strict'|'none')

    """
    content_type: Optional[str] = None
    status_code: int = HTTPStatus.OK.value

    def __init__(
        self,
        content,
        *,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        cookies: Optional[dict[str, str]] = None,
    ):
        """Setup the response."""
        self.content = self.process_content(content)
        self.headers: MultiDict = MultiDict(headers or {})
        self.cookies: SimpleCookie = SimpleCookie(cookies)
        if status_code is not None:
            self.status_code = status_code

        content_type = content_type or self.content_type
        if content_type:
            self.headers.setdefault(
                "content-type",
                content_type.startswith("text/")
                and f"{content_type}; charset={DEFAULT_CHARSET}"
                or content_type,
            )

    def __str__(self) -> str:
        """Stringify the response."""
        return f"{self.status_code}"

    def __repr__(self) -> str:
        """Stringify the response."""
        return f"<{ self.__class__.__name__ } '{ self }'>"

    async def __call__(self, _, __, send: TASGISend):
        """Behave as an ASGI application."""
        self.headers.setdefault("content-length", str(len(self.content)))

        await send(self.msg_start())
        await send({"type": "http.response.body", "body": self.content})

    @staticmethod
    def process_content(content) -> bytes:
        if not isinstance(content, bytes):
            return str(content).encode(DEFAULT_CHARSET)
        return content

    def msg_start(self) -> TASGIMessage:
        """Get ASGI response start message."""
        headers = [
            (key.encode(BASE_ENCODING), str(val).encode(BASE_ENCODING))
            for key, val in self.headers.items()
        ]

        for cookie in self.cookies.values():
            headers = [
                *headers,
                (b"set-cookie", cookie.output(header="").strip().encode(BASE_ENCODING)),
            ]

        return {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": headers,
        }


class ResponseText(Response):
    """A helper to return plain text responses (text/plain)."""

    content_type = "text/plain"


class ResponseHTML(Response):
    """A helper to return HTML responses (text/html)."""

    content_type = "text/html"


class ResponseJSON(Response):
    """A helper to return JSON responses (application/json).

    The class optionally supports `ujson <https://pypi.org/project/ujson/>`_ and `orjson
    <https://pypi.org/project/orjson/>`_ JSON libraries. Install one of them to use instead
    the standard library.

    """

    content_type = "application/json"

    @staticmethod
    def process_content(content) -> bytes:
        """Dumps the given content."""
        return json_dumps(content)


class ResponseStream(Response):
    """A helper to stream a response's body.

    :param content: An async generator to stream the response's body
    :type content: AsyncGenerator
    """

    def __init__(self, stream: AsyncGenerator[Any, None], **kwargs):
        super().__init__(b"", **kwargs)
        self.stream = stream

    async def listen_for_disconnect(self, receive: TASGIReceive):
        """Listen for the client has been disconnected."""
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break

    async def stream_response(self, send: TASGISend):
        """Stream response content."""
        await send(self.msg_start())
        async for chunk in self.stream:
            await send(
                {
                    "type": "http.response.body",
                    "body": self.process_content(chunk),
                    "more_body": True,
                },
            )

        await send({"type": "http.response.body", "body": b""})

    async def __call__(self, _, receive, send: TASGISend) -> None:
        """Behave as an ASGI application."""
        await aio_wait(
            self.listen_for_disconnect(receive),
            self.stream_response(send),
            strategy=FIRST_COMPLETED,
        )


class ResponseSSE(ResponseStream):
    """A helper to stream SSE (server side events).

    :param content: An async generator to stream the events
    :type content: AsyncGenerator
    """

    content_type = "text/event-stream"

    def msg_start(self) -> TASGIMessage:
        """Set cache-control header."""
        self.headers.setdefault("Cache-Control", "no-cache")
        return super().msg_start()

    @staticmethod
    def process_content(chunk) -> bytes:
        """Prepare a chunk from stream generator to send."""
        if isinstance(chunk, dict):
            chunk = "\n".join(f"{k}: {v}" for k, v in chunk.items())

        if not isinstance(chunk, bytes):
            chunk = chunk.encode(DEFAULT_CHARSET)

        return chunk + b"\n\n"


class ResponseFile(ResponseStream):
    """A helper to stream files as a response body.

    :param filepath: The filepath to the file
    :type filepath: str | Path
    :param chunk_size: Default chunk size (32768)
    :type chunk_size: int
    :param filename: If set, `Content-Disposition` header will be generated
    :type filename: str
    :param headers_only: Return only file headers
    :type headers_only: bool

    """

    def __init__(
        self,
        filepath: Union[str, Path],
        *,
        chunk_size: int = 64 * 1024,
        filename: Optional[str] = None,
        headers_only: bool = False,
        **kwargs,
    ) -> None:
        """Store filepath to self."""
        try:
            stat = Path(filepath).stat()
        except FileNotFoundError as exc:
            raise ASGIError(*exc.args) from exc

        if S_ISDIR(stat.st_mode):
            raise ASGIError(f"It's a directory: {filepath}")  # noqa: TRY003

        super().__init__(
            empty() if headers_only else aio_stream_file(filepath, chunk_size),
            **kwargs,
        )

        headers = self.headers
        if filename and "content-disposition" not in headers:
            headers["content-disposition"] = f'attachment; filename="{quote(filename)}"'

        if "content-type" not in headers:
            headers["content-type"] = guess_type(filename or str(filepath))[0] or "text/plain"

        headers.setdefault("content-length", str(stat.st_size))
        headers.setdefault("last-modified", formatdate(stat.st_mtime, usegmt=True))
        etag = str(stat.st_mtime) + "-" + str(stat.st_size)
        headers.setdefault("etag", md5(etag.encode()).hexdigest())  # noqa: S324


class ResponseWebSocket(Response):
    """A helper to work with websockets.

    :param scope: Request info (ASGI Scope | ASGI-Tools Request)
    :type scope: dict
    :param receive: ASGI receive function
    :param send: ASGI send function
    """

    class STATES(Enum):
        """Represent websocket states."""

        CONNECTING = 0
        CONNECTED = 1
        DISCONNECTED = 2

    def __init__(
        self,
        scope: TASGIScope,
        receive: Optional[TASGIReceive] = None,
        send: Optional[TASGISend] = None,
    ) -> None:
        """Initialize the websocket response."""
        if isinstance(scope, Request):
            receive, send = scope.receive, scope.send

        if not receive or not send:
            raise ASGIError("Invalid initialization")  # noqa: TRY003

        super().__init__(b"")
        self._receive: TASGIReceive = receive
        self._send: TASGISend = send
        self.state = self.STATES.CONNECTING
        self.partner_state = self.STATES.CONNECTING

    async def __call__(self, _, __, send: TASGISend):
        """Close websocket if the response has been returned."""
        await send({"type": "websocket.close"})

    async def __aenter__(self):
        """Use it as async context manager."""
        await self.accept()
        return self

    async def __aexit__(self, *_):
        """Use it as async context manager."""
        await self.close()

    @property
    def connected(self) -> bool:
        """Check that is the websocket connected."""
        return self.state == self.partner_state == self.STATES.CONNECTED

    async def _connect(self) -> bool:
        """Wait for connect message."""
        if self.partner_state == self.STATES.CONNECTING:
            msg = await self._receive()
            assert msg.get("type") == "websocket.connect"
            self.partner_state = self.STATES.CONNECTED

        return self.partner_state == self.STATES.CONNECTED

    async def accept(self, **params) -> None:
        """Accept a websocket connection."""
        if self.partner_state == self.STATES.CONNECTING:
            await self._connect()

        await self.send({"type": "websocket.accept", **params})
        self.state = self.STATES.CONNECTED

    async def close(self, code: int = 1000) -> None:
        """Sent by the application to tell the server to close the connection."""
        if self.connected:
            await self.send({"type": "websocket.close", "code": code})
        self.state = self.STATES.DISCONNECTED

    async def send(self, msg: Union[dict, str, bytes], msg_type="websocket.send") -> None:
        """Send the given message to a client."""
        if self.state == self.STATES.DISCONNECTED:
            raise ASGIConnectionClosedError

        if not isinstance(msg, dict):
            msg = {"type": msg_type, (isinstance(msg, str) and "text" or "bytes"): msg}

        return await self._send(msg)

    async def send_json(self, data) -> None:
        """Serialize the given data to JSON and send to a client."""
        return await self._send({"type": "websocket.send", "bytes": json_dumps(data)})

    async def receive(self, *, raw: bool = False) -> Union[TASGIMessage, str]:
        """Receive messages from a client.

        :param raw: Receive messages as is.
        """
        if self.partner_state == self.STATES.DISCONNECTED:
            raise ASGIConnectionClosedError

        if self.partner_state == self.STATES.CONNECTING:
            await self._connect()
            return await self.receive(raw=raw)

        msg = await self._receive()
        if msg["type"] == "websocket.disconnect":
            self.partner_state = self.STATES.DISCONNECTED

        return msg if raw else parse_websocket_msg(msg, charset=DEFAULT_CHARSET)


class ResponseRedirect(Response, BaseException):
    """A helper to return HTTP redirects. Uses a 307 status code by default.

    :param url: A string with the new location
    :type url: str
    """

    status_code: int = HTTPStatus.TEMPORARY_REDIRECT.value

    def __init__(self, url: str, status_code: Optional[int] = None, **kwargs) -> None:
        """Set status code and prepare location."""
        super().__init__(b"", status_code=status_code, **kwargs)
        assert (
            300 <= self.status_code < 400
        ), f"Invalid status code for redirection: {self.status_code}"
        self.headers["location"] = quote_plus(url, safe=":/%#?&=@[]!$&'()*+,;")


class ResponseErrorMeta(type):
    """Generate Response Errors by HTTP names."""

    # TODO: From python 3.9 -> partial['ResponseError]
    def __getattr__(cls, name: str) -> Callable[..., ResponseError]:
        """Generate Response Errors by HTTP names."""
        status = HTTPStatus[name]
        return partial(
            lambda *args, **kwargs: cls(*args, **kwargs),
            status_code=status.value,
        )


class ResponseError(Response, BaseException, metaclass=ResponseErrorMeta):
    """A helper to return HTTP errors. Uses a 500 status code by default.

    :param message: A string with the error's message (HTTPStatus messages will be used by default)
    :type message: str

    You able to use :py:class:`http.HTTPStatus` properties with the `ResponseError` class

    .. code-block:: python

        response = ResponseError.BAD_REQUEST('invalid data')
        response = ResponseError.NOT_FOUND()
        response = ResponseError.BAD_GATEWAY()
        # and etc

    """

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value

    # Typing annotations
    if TYPE_CHECKING:
        BAD_REQUEST: Callable[..., ResponseError]  # 400
        UNAUTHORIZED: Callable[..., ResponseError]  # 401
        PAYMENT_REQUIRED: Callable[..., ResponseError]  # 402
        FORBIDDEN: Callable[..., ResponseError]  # 403
        NOT_FOUND: Callable[..., ResponseError]  # 404
        METHOD_NOT_ALLOWED: Callable[..., ResponseError]  # 405
        NOT_ACCEPTABLE: Callable[..., ResponseError]  # 406
        PROXY_AUTHENTICATION_REQUIRED: Callable[..., ResponseError]  # 407
        REQUEST_TIMEOUT: Callable[..., ResponseError]  # 408
        CONFLICT: Callable[..., ResponseError]  # 409
        GONE: Callable[..., ResponseError]  # 410
        LENGTH_REQUIRED: Callable[..., ResponseError]  # 411
        PRECONDITION_FAILED: Callable[..., ResponseError]  # 412
        REQUEST_ENTITY_TOO_LARGE: Callable[..., ResponseError]  # 413
        REQUEST_URI_TOO_LONG: Callable[..., ResponseError]  # 414
        UNSUPPORTED_MEDIA_TYPE: Callable[..., ResponseError]  # 415
        REQUESTED_RANGE_NOT_SATISFIABLE: Callable[..., ResponseError]  # 416
        EXPECTATION_FAILED: Callable[..., ResponseError]  # 417
        # TODO: From python 3.9
        # IM_A_TEAPOT: Callable[..., ResponseError]                       # 418
        # MISDIRECTED_REQUEST: Callable[..., ResponseError]               # 421
        UNPROCESSABLE_ENTITY: Callable[..., ResponseError]  # 422
        LOCKED: Callable[..., ResponseError]  # 423
        FAILED_DEPENDENCY: Callable[..., ResponseError]  # 424
        TOO_EARLY: Callable[..., ResponseError]  # 425
        UPGRADE_REQUIRED: Callable[..., ResponseError]  # 426
        PRECONDITION_REQUIRED: Callable[..., ResponseError]  # 428
        TOO_MANY_REQUESTS: Callable[..., ResponseError]  # 429
        REQUEST_HEADER_FIELDS_TOO_LARGE: Callable[..., ResponseError]  # 431
        # TODO: From python 3.9
        # UNAVAILABLE_FOR_LEGAL_REASONS: Callable[..., ResponseError]     # 451

        INTERNAL_SERVER_ERROR: Callable[..., ResponseError]  # 500
        NOT_IMPLEMENTED: Callable[..., ResponseError]  # 501
        BAD_GATEWAY: Callable[..., ResponseError]  # 502
        SERVICE_UNAVAILABLE: Callable[..., ResponseError]  # 503
        GATEWAY_TIMEOUT: Callable[..., ResponseError]  # 504
        HTTP_VERSION_NOT_SUPPORTED: Callable[..., ResponseError]  # 505
        VARIANT_ALSO_NEGOTIATES: Callable[..., ResponseError]  # 506
        INSUFFICIENT_STORAGE: Callable[..., ResponseError]  # 507
        LOOP_DETECTED: Callable[..., ResponseError]  # 508
        NOT_EXTENDED: Callable[..., ResponseError]  # 510
        NETWORK_AUTHENTICATION_REQUIRED: Callable[..., ResponseError]  # 511

    def __init__(self, message=None, status_code: Optional[int] = None, **kwargs):
        """Check error status."""
        content = message or HTTPStatus(status_code or self.status_code).description
        super().__init__(content=content, status_code=status_code, **kwargs)
        assert self.status_code >= 400, f"Invalid status code for an error: {self.status_code}"


CAST_RESPONSE: Mapping[type, type[Response]] = {
    bool: ResponseJSON,
    bytes: ResponseHTML,
    dict: ResponseJSON,
    int: ResponseJSON,
    list: ResponseJSON,
    str: ResponseHTML,
    type(None): ResponseJSON,
}


def parse_response(response, headers: Optional[dict] = None) -> Response:
    """Parse the given object and convert it into a asgi_tools.Response."""
    if isinstance(response, Response):
        return response

    rtype = type(response)
    response_type = CAST_RESPONSE.get(rtype)
    if response_type:
        return response_type(response, headers=headers)

    if rtype is tuple:
        status, *contents = response
        assert isinstance(status, int), "Invalid Response Status"
        if len(contents) > 1:
            headers, *contents = contents
        response = parse_response(
            contents[0] or "" if contents else "",
            headers=headers,
        )
        response.status_code = status
        return response

    return ResponseText(str(response), headers=headers)


def parse_websocket_msg(
    msg: TASGIMessage, charset: Optional[str] = None
) -> Union[TASGIMessage, str]:
    """Prepare websocket message."""
    data = msg.get("text")
    if data:
        return data

    data = msg.get("bytes")
    if data:
        return data.decode(charset)

    return msg


async def empty():
    yield b""


# ruff: noqa: ERA001
