"""ASGI responses."""

import os
from enum import Enum
from inspect import isasyncgen
from http import cookies, HTTPStatus
from json import dumps
from urllib.parse import quote_plus
from pathlib import Path
from email.utils import formatdate
from mimetypes import guess_type
from hashlib import md5
import typing as t

from multidict import CIMultiDict
from sniffio import current_async_library

from . import DEFAULT_CHARSET, ASGIError, ASGIConnectionClosed
from .request import Request
from .utils import aiofile, trio
from .types import Message, ResponseContent, Scope, Receive, Send


class Response:
    """ASGI Response."""

    charset: str = DEFAULT_CHARSET

    #  __slots__ = 'content', 'status_code', 'headers', 'cookies'

    def __init__(
            self, content: ResponseContent = None, status_code: int = HTTPStatus.OK.value,
            headers: dict = None, content_type: str = None) -> None:
        """Setup the response."""
        self.content = content
        self.status_code = status_code
        self.headers: CIMultiDict = CIMultiDict(headers or {})
        self.cookies: cookies.SimpleCookie = cookies.SimpleCookie()
        if content_type:
            if content_type.startswith('text/'):
                content_type = f"{content_type}; charset={self.charset}"

            self.headers['content-type'] = content_type

    def __str__(self) -> str:
        """Stringify the response."""
        return f"{self.status_code}"

    def __repr__(self) -> str:
        """Stringify the response."""
        return f"<{ self.__class__.__name__ } '{ self }'"

    async def __aiter__(self) -> t.AsyncGenerator:
        """Iterate self through ASGI messages."""
        self.headers.setdefault('content-length', str(len(self.body)))

        yield self.msg_start()
        yield self.msg_body(self.body)

    async def __call__(self, scope: t.Any, receive: t.Any, send: Send) -> None:
        """Behave as an ASGI application."""
        async for message in self:
            await send(message)

    @property
    def body(self) -> bytes:
        """Create a response body."""
        if self.content is None:
            return b""

        if isinstance(self.content, bytes):
            return self.content

        return self.content.encode(self.charset)

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

    def msg_body(self, body: bytes, /, more_body: bool = False) -> Message:
        """Get ASGI response body message."""
        return {"type": "http.response.body", "body": body, "more_body": more_body}

    def msg_end(self) -> Message:
        """Get ASGI response finish message."""
        return self.msg_body(b'')


class ResponseText(Response):
    """Plain-text Response."""

    def __init__(self, *args, **kwargs) -> None:
        """Setup the response."""
        kwargs['content_type'] = 'text/plain'
        super().__init__(*args, **kwargs)


class ResponseHTML(Response):
    """HTML Response."""

    def __init__(self, *args, **kwargs) -> None:
        """Setup the response."""
        kwargs['content_type'] = 'text/html'
        super().__init__(*args, **kwargs)


class ResponseJSON(Response):
    """JSON Response."""

    def __init__(self, *args, **kwargs) -> None:
        """Setup the response."""
        kwargs['content_type'] = 'application/json'
        super().__init__(*args, **kwargs)

    @property
    def body(self) -> bytes:
        """Jsonify the content."""
        return dumps(self.content, ensure_ascii=False, allow_nan=False).encode(self.charset)


class ResponseRedirect(Response, BaseException):
    """Redirect Response."""

    def __init__(self, url: str,
                 status_code: int = HTTPStatus.TEMPORARY_REDIRECT.value, **kwargs) -> None:
        """Set status code and prepare location."""
        if not (300 <= status_code < 400):
            raise ASGIError(f"Invalid status_code ({status_code}).")

        super(ResponseRedirect, self).__init__(status_code=status_code, **kwargs)
        self.headers["location"] = quote_plus(str(url), safe=":/%#?&=@[]!$&'()*+,;")


class ResponseError(Response, BaseException):
    """Raise `ErrorResponse` to stop processing and return HTTP Error Response."""

    def __init__(self, status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR.value,
                 content: ResponseContent = None, **kwargs):
        """Check error status."""
        if status_code < 400:
            raise ASGIError(f"Invalid status_code ({status_code}).")
        content = content or HTTPStatus(status_code).description
        super(ResponseError, self).__init__(content=content, status_code=status_code, **kwargs)


class ResponseStream(Response):
    """Stream response."""

    def __init__(self, content: t.AsyncGenerator[ResponseContent, None], **kwargs) -> None:
        """Ensure that the content is awaitable."""
        assert isasyncgen(content), "Content have to be awaitable"
        super(ResponseStream, self).__init__(**kwargs)
        self.content: t.AsyncGenerator[ResponseContent, None] = content  # type: ignore

    async def __aiter__(self) -> t.AsyncGenerator[Message, None]:
        """Iterate through the response."""
        yield self.msg_start()

        async for chunk in self.content:
            if not isinstance(chunk, bytes):
                chunk = str(chunk).encode(self.charset)
            yield self.msg_body(chunk, more_body=True)

        yield self.msg_end()


class ResponseFile(Response):
    """Read and stream a file."""

    def __init__(self, filepath: t.Union[str, Path], chunk_size: int = 32 * 1024,
                 headers_only: bool = False, **kwargs) -> None:
        """Store filepath to self."""
        super(ResponseFile, self).__init__(**kwargs)
        self.chunk_size = chunk_size
        self.headers_only = headers_only
        self.filepath: Path = Path(filepath)
        try:
            stat = os.stat(filepath)
        except FileNotFoundError as exc:
            raise ASGIError(*exc.args)

        self.headers.setdefault(
            'content-disposition', f'attachment; filename="{self.filepath.name}"')
        self.headers.setdefault('content-type', guess_type(self.filepath)[0] or "text/plain")
        self.headers.setdefault('content-length', str(stat.st_size))
        self.headers.setdefault('last-modified', formatdate(stat.st_mtime, usegmt=True))
        etag = str(stat.st_mtime) + "-" + str(stat.st_size)
        self.headers.setdefault('etag', md5(etag.encode()).hexdigest())

    async def __aiter__(self) -> t.AsyncGenerator[Message, None]:
        """Iterate throug the file."""
        yield self.msg_start()
        if not self.headers_only:
            if current_async_library() == 'trio':
                async with await trio.open_file(self.filepath, 'rb') as fp:
                    while chunk := await fp.read(self.chunk_size):
                        yield self.msg_body(chunk, more_body=True)

            else:
                if aiofile is None:
                    raise ASGIError('`aiofile` is required to return files with asyncio')

                async with aiofile.AIOFile(self.filepath, mode='rb') as fp:
                    async for chunk in aiofile.Reader(fp, chunk_size=self.chunk_size):
                        yield self.msg_body(chunk, more_body=True)

        yield self.msg_end()


class ResponseWebSocket(Response):
    """Work with websockets."""

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

    async def __aiter__(self) -> t.AsyncGenerator[Message, None]:
        """Close websocket if the response has been returned."""
        yield {'type': 'websocket.close'}

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


async def parse_response(response: t.Any, headers: t.Dict = None) -> Response:
    """Parse the given object and convert it into a asgi_tools.Response."""

    if isinstance(response, Response):
        return response

    if isinstance(response, (str, bytes)):
        return ResponseHTML(response, headers=headers)

    if isinstance(response, tuple):
        status, *contents = response
        if len(contents) > 1:
            headers, *contents = contents
        response = await parse_response(contents[0] or '' if contents else '', headers=headers)
        response.status_code = status
        return response

    if response is None or isinstance(response, (dict, list, int, bool)):
        return ResponseJSON(response, headers=headers)

    return ResponseText(str(response), headers=headers)


def parse_websocket_msg(msg: Message, charset: str = None) -> t.Union[Message, str]:
    """Prepare websocket message."""
    if data := msg.get('text'):
        return data

    if data := msg.get('bytes'):
        return data.decode(charset)

    return msg
