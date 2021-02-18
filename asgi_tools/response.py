"""ASGI responses."""

from email.utils import formatdate
from enum import Enum
from functools import partial
from hashlib import md5
from http import cookies, HTTPStatus
from json import dumps
from mimetypes import guess_type
from multidict import CIMultiDict
from pathlib import Path
from urllib.parse import quote_plus
import os
import typing as t

from sniffio import current_async_library

from . import DEFAULT_CHARSET, ASGIError, ASGIConnectionClosed
from ._compat import aiofile, trio, wait_for_first
from ._types import Message, ResponseContent, Scope, Receive, Send
from .request import Request


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
    """

    headers: CIMultiDict  #: Multidict of response's headers
    cookies: cookies.SimpleCookie
    """ Set/Update cookies

    * `response.cookies[name] = value` ``str`` -- set a cookie's value
    * `response.cookies[name]['path'] = value` ``str`` -- set a cookie's path
    * `response.cookies[name]['expires'] = value` ``int`` -- set a cookie's expire
    * `response.cookies[name]['domain'] = value` ``str`` -- set a cookie's domain
    * `response.cookies[name]['max-age'] = value` ``int`` -- set a cookie's max-age
    * `response.cookies[name]['secure'] = value` ``bool``-- is the cookie should only be sent if request is SSL
    * `response.cookies[name]['httponly'] = value` ``bool`` -- is the cookie should be available through HTTP request only (not from JS)
    * `response.cookies[name]['samesite'] = value` ``str`` -- set a cookie's strategy ('lax'|'strict'|'none')

    """
    charset: str = DEFAULT_CHARSET
    content_type: t.Optional[str] = None

    #  __slots__ = 'content', 'status_code', 'headers', 'cookies'

    def __init__(
            self, content: ResponseContent = None, status_code: int = HTTPStatus.OK.value,
            headers: dict = None, content_type: str = None):
        """Setup the response."""
        self.content = content
        self.status_code = status_code
        self.headers: CIMultiDict = CIMultiDict(headers or {})
        self.cookies: cookies.SimpleCookie = cookies.SimpleCookie()
        if content_type is not None:
            self.content_type = content_type

        if self.content_type:
            self.headers.setdefault(
                'content-type', self.content_type.startswith('text/') and
                f"{self.content_type}; charset={self.charset}" or self.content_type
            )

    def __str__(self) -> str:
        """Stringify the response."""
        return f"{self.status_code}"

    def __repr__(self) -> str:
        """Stringify the response."""
        return f"<{ self.__class__.__name__ } '{ self }'"

    async def __call__(self, scope: t.Any, receive: t.Any, send: Send) -> None:
        """Behave as an ASGI application."""
        self.headers.setdefault('content-length', str(len(self.__content__)))

        await send(self.msg_start())
        await send({"type": "http.response.body", "body": self.__content__})

    @property
    def content(self):
        """Get self content."""
        return self.__content__

    @content.setter
    def content(self, content: ResponseContent):
        # py38 return :=
        if isinstance(content, str):
            self.__content__ = content.encode(self.charset)

        elif content is None:
            self.__content__ = b""

        elif isinstance(content, bytes):
            self.__content__ = content

        else:
            self.__content__ = str(content).encode(self.charset)

    def msg_start(self) -> Message:
        """Get ASGI response start message."""
        headers = [
            (key.lower().encode('latin-1'), str(val).encode('latin-1'))
            for key, val in self.headers.items()
        ]

        for cookie in self.cookies.values():
            headers.append((b"set-cookie", cookie.output(header='').strip().encode('latin-1')))

        return {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": headers,
        }


class ResponseText(Response):
    """A helper to return plain text responses (text/plain)."""

    content_type = 'text/plain'


class ResponseHTML(Response):
    """A helper to return HTML responses (text/html)."""

    content_type = 'text/html'


class ResponseJSON(Response):
    """A helper to return JSON responses (application/json)."""

    content_type = 'application/json'

    @Response.content.setter  # type: ignore
    def content(self, content: ResponseContent):
        """Jsonify the content."""
        self.__content__ = dumps(content, ensure_ascii=False, allow_nan=False).encode(self.charset)


class ResponseRedirect(Response, BaseException):
    """A helper to return HTTP redirects. Uses a 307 status code by default.

    :param url: A string with the new location
    :type url: str
    """

    def __init__(self, url: str,
                 status_code: int = HTTPStatus.TEMPORARY_REDIRECT.value, **kwargs) -> None:
        """Set status code and prepare location."""
        if not (300 <= status_code < 400):
            raise ASGIError(f"Invalid status_code ({status_code}).")

        super(ResponseRedirect, self).__init__(status_code=status_code, **kwargs)
        self.headers["location"] = quote_plus(str(url), safe=":/%#?&=@[]!$&'()*+,;")


class ResponseErrorMeta(type):
    """Generate Response Errors by HTTP names."""

    # XXX: From python 3.9 -> partial['ResponseError]
    def __getattr__(cls, name: str) -> t.Callable[..., 'ResponseError']:
        """Generate Response Errors by HTTP names."""
        status = HTTPStatus[name]
        return partial(cls, status_code=status.value)


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

    # Typing annotations
    BAD_REQUEST: t.Callable[..., 'ResponseError']                       # 400
    UNAUTHORIZED: t.Callable[..., 'ResponseError']                      # 401
    PAYMENT_REQUIRED: t.Callable[..., 'ResponseError']                  # 402
    FORBIDDEN: t.Callable[..., 'ResponseError']                         # 403
    NOT_FOUND: t.Callable[..., 'ResponseError']                         # 404
    METHOD_NOT_ALLOWED: t.Callable[..., 'ResponseError']                # 405
    NOT_ACCEPTABLE: t.Callable[..., 'ResponseError']                    # 406
    PROXY_AUTHENTICATION_REQUIRED: t.Callable[..., 'ResponseError']     # 407
    REQUEST_TIMEOUT: t.Callable[..., 'ResponseError']                   # 408
    CONFLICT: t.Callable[..., 'ResponseError']                          # 409
    GONE: t.Callable[..., 'ResponseError']                              # 410
    LENGTH_REQUIRED: t.Callable[..., 'ResponseError']                   # 411
    PRECONDITION_FAILED: t.Callable[..., 'ResponseError']               # 412
    REQUEST_ENTITY_TOO_LARGE: t.Callable[..., 'ResponseError']          # 413
    REQUEST_URI_TOO_LONG: t.Callable[..., 'ResponseError']              # 414
    UNSUPPORTED_MEDIA_TYPE: t.Callable[..., 'ResponseError']            # 415
    REQUESTED_RANGE_NOT_SATISFIABLE: t.Callable[..., 'ResponseError']   # 416
    EXPECTATION_FAILED: t.Callable[..., 'ResponseError']                # 417
    # XXX: From python 3.9
    # IM_A_TEAPOT: t.Callable[..., 'ResponseError']                       # 418
    # MISDIRECTED_REQUEST: t.Callable[..., 'ResponseError']               # 421
    UNPROCESSABLE_ENTITY: t.Callable[..., 'ResponseError']              # 422
    LOCKED: t.Callable[..., 'ResponseError']                            # 423
    FAILED_DEPENDENCY: t.Callable[..., 'ResponseError']                 # 424
    TOO_EARLY: t.Callable[..., 'ResponseError']                         # 425
    UPGRADE_REQUIRED: t.Callable[..., 'ResponseError']                  # 426
    PRECONDITION_REQUIRED: t.Callable[..., 'ResponseError']             # 428
    TOO_MANY_REQUESTS: t.Callable[..., 'ResponseError']                 # 429
    REQUEST_HEADER_FIELDS_TOO_LARGE: t.Callable[..., 'ResponseError']   # 431
    # XXX: From python 3.9
    # UNAVAILABLE_FOR_LEGAL_REASONS: t.Callable[..., 'ResponseError']     # 451

    INTERNAL_SERVER_ERROR: t.Callable[..., 'ResponseError']             # 500
    NOT_IMPLEMENTED: t.Callable[..., 'ResponseError']                   # 501
    BAD_GATEWAY: t.Callable[..., 'ResponseError']                       # 502
    SERVICE_UNAVAILABLE: t.Callable[..., 'ResponseError']               # 503
    GATEWAY_TIMEOUT: t.Callable[..., 'ResponseError']                   # 504
    HTTP_VERSION_NOT_SUPPORTED: t.Callable[..., 'ResponseError']        # 505
    VARIANT_ALSO_NEGOTIATES: t.Callable[..., 'ResponseError']           # 506
    INSUFFICIENT_STORAGE: t.Callable[..., 'ResponseError']              # 507
    LOOP_DETECTED: t.Callable[..., 'ResponseError']                     # 508
    NOT_EXTENDED: t.Callable[..., 'ResponseError']                      # 510
    NETWORK_AUTHENTICATION_REQUIRED: t.Callable[..., 'ResponseError']   # 511

    def __init__(self, message: ResponseContent = None,
                 status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value, **kwargs):
        """Check error status."""
        if status_code < 400:
            raise ASGIError(f"Invalid status_code ({status_code}).")
        message = message or HTTPStatus(status_code).description
        super(ResponseError, self).__init__(content=message, status_code=status_code, **kwargs)


class ResponseStream(Response):
    """A helper to stream a response's body.

    :param content: An async generator to stream the response's body
    :type content: AsyncGenerator
    """

    @Response.content.setter  # type: ignore
    def content(self, content: t.AsyncGenerator[ResponseContent, None] = None):
        """Store self content as is."""
        self.__content__ = content  # type: ignore

    async def listen_for_disconnect(self, receive: Receive):
        """Listen for the client has been disconnected."""
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                break

    async def stream_response(self, send: Send):
        """Stream response content."""
        await send(self.msg_start())
        if self.content:
            async for chunk in self.content:
                if not isinstance(chunk, bytes):
                    chunk = str(chunk).encode(self.charset)
                await send({"type": "http.response.body", "body": chunk, "more_body": True})

        await send({"type": "http.response.body", "body": b""})

    async def __call__(self, scope: t.Any, receive: t.Any, send: Send) -> None:
        """Behave as an ASGI application."""
        await wait_for_first(
            self.listen_for_disconnect(receive),
            self.stream_response(send),
        )


class ResponseFile(ResponseStream):
    """A helper to stream files as a response body."""

    def __init__(self, filename: t.Union[str, Path], chunk_size: int = 32 * 1024,
                 headers_only: bool = False, **kwargs) -> None:
        """Store filepath to self."""
        filepath: Path = Path(filename)
        try:
            stat = os.stat(filepath)
        except FileNotFoundError as exc:
            raise ASGIError(*exc.args)

        stream = stream_file(filepath, chunk_size) if not headers_only else None
        super(ResponseFile, self).__init__(stream, **kwargs)  # type: ignore
        self.headers_only = headers_only
        self.headers.setdefault(
            'content-disposition', f'attachment; filename="{filepath.name}"')
        self.headers.setdefault('content-type', guess_type(str(filepath))[0] or "text/plain")
        self.headers.setdefault('content-length', str(stat.st_size))
        self.headers.setdefault('last-modified', formatdate(stat.st_mtime, usegmt=True))
        etag = str(stat.st_mtime) + "-" + str(stat.st_size)
        self.headers.setdefault('etag', md5(etag.encode()).hexdigest())


class ResponseWebSocket(Response):
    """A helper to work with websockets."""

    class STATES(Enum):
        """Represent websocket states."""

        connecting = 0
        connected = 1
        disconnected = 2

    def __init__(self, scope: Scope, receive: Receive = None, send: Send = None) -> None:
        """Initialize the websocket response."""
        if isinstance(scope, Request):
            receive, send = scope._receive, scope._send

        super(ResponseWebSocket, self).__init__()
        assert receive and send, 'Invalid initialization'
        self._receive: Receive = receive
        self._send: Send = send
        self.state = self.STATES.connecting
        self.partner_state = self.STATES.connecting

    async def __call__(self, scope: t.Any, receive: t.Any, send: Send):
        """Close websocket if the response has been returned."""
        await send({'type': 'websocket.close'})

    async def __aenter__(self):
        """Use it as async context manager."""
        await self.accept()
        return self

    async def __aexit__(self, *args):
        """Use it as async context manager."""
        await self.close()

    @property
    def connected(self) -> bool:
        """Check that is the websocket connected."""
        return self.state == self.STATES.connected and self.partner_state == self.STATES.connected

    async def _connect(self) -> bool:
        """Wait for connect message."""
        if self.partner_state == self.STATES.connecting:
            msg = await self._receive()
            assert msg.get('type') == 'websocket.connect'
            self.partner_state = self.STATES.connected

        return self.partner_state == self.STATES.connected

    async def accept(self, **params) -> None:
        """Accept a websocket connection."""
        if self.partner_state == self.STATES.connecting:
            await self._connect()

        await self.send({'type': 'websocket.accept', **params})
        self.state = self.STATES.connected

    async def close(self, code=1000) -> None:
        """Sent by the application to tell the server to close the connection."""
        if self.connected:
            await self.send({'type': 'websocket.close', 'code': code})
        self.state = self.STATES.disconnected

    def send(self, msg, type='websocket.send') -> t.Awaitable:
        """Send the given message to a client."""
        if self.state == self.STATES.disconnected:
            raise ASGIConnectionClosed('Cannot send once the connection has been disconnected.')

        if not isinstance(msg, dict):
            msg = {'type': type, (isinstance(msg, str) and 'text' or 'bytes'): msg}

        return self._send(msg)

    async def receive(self, raw: bool = False) -> t.Union[Message, str]:
        """Receive messages from a client."""
        if self.partner_state == self.STATES.disconnected:
            raise ASGIConnectionClosed('Cannot receive once a connection has been disconnected.')

        if self.partner_state == self.STATES.connecting:
            await self._connect()
            return await self.receive(raw=raw)

        msg = await self._receive()
        if msg['type'] == 'websocket.disconnect':
            self.partner_state = self.STATES.disconnected

        return raw and msg or parse_websocket_msg(msg, charset=self.charset)


CAST_RESPONSE: t.Dict[t.Type, t.Type[Response]] = {
    bool: ResponseJSON,
    bytes: ResponseHTML,
    dict: ResponseJSON,
    int: ResponseJSON,
    list: ResponseJSON,
    str: ResponseHTML,
    type(None): ResponseJSON,
}


def parse_response(response: t.Any, headers: t.Dict = None) -> Response:
    """Parse the given object and convert it into a asgi_tools.Response."""

    rtype = type(response)
    if issubclass(rtype, Response):
        return response

    ResponseType = CAST_RESPONSE.get(rtype)
    if ResponseType:
        return ResponseType(response, headers=headers)

    if rtype is tuple:
        status, *contents = response
        assert isinstance(status, int), 'Invalid Response Status'
        if len(contents) > 1:
            headers, *contents = contents
        response = parse_response(contents[0] or '' if contents else '', headers=headers)
        response.status_code = status
        return response

    return ResponseText(str(response), headers=headers)


def parse_websocket_msg(msg: Message, charset: str = None) -> t.Union[Message, str]:
    """Prepare websocket message."""
    data = msg.get('text')
    if data:
        return data

    data = msg.get('bytes')
    if data:
        return data.decode(charset)

    return msg


async def stream_file(filepath: t.Union[str, Path], chunk_size: int = 32 * 1024) -> t.AsyncGenerator[bytes, None]:  # noqa
    """Stream the given file."""
    if current_async_library() == 'trio':
        async with await trio.open_file(filepath, 'rb') as fp:
            while True:
                chunk = await fp.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    else:
        if aiofile is None:
            raise ASGIError('`aiofile` is required to return files with asyncio')

        async with aiofile.AIOFile(filepath, mode='rb') as fp:
            async for chunk in aiofile.Reader(fp, chunk_size=chunk_size):
                yield chunk

# pylama: ignore=E501
