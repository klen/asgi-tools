"""ASGI responses."""

import os
from inspect import isawaitable, isasyncgen
from http import cookies, HTTPStatus
from json import dumps
from urllib.parse import quote_plus
from pathlib import Path
from email.utils import formatdate
from mimetypes import guess_type
from hashlib import md5

from multidict import CIMultiDict
from sniffio import current_async_library

from . import DEFAULT_CHARSET, ASGIError
from .utils import aiofile, trio


class Response:
    """ASGI Response."""

    charset = DEFAULT_CHARSET

    def __init__(
            self, content=None, status_code=HTTPStatus.OK.value, headers=None, content_type=None):
        """Setup the response."""
        self.content = content
        self.status_code = status_code
        self.headers = CIMultiDict(headers or {})
        self.cookies = cookies.SimpleCookie()
        if content_type:
            if content_type.startswith('text/'):
                content_type = f"{content_type}; charset={self.charset}"

            self.headers['content-type'] = content_type

    def __str__(self):
        """Stringify the response."""
        return f"{self.status_code}"

    def __repr__(self):
        """Stringify the response."""
        return f"<Response '{ self }'"

    async def __aiter__(self):
        """Iterate self through ASGI messages."""
        self.headers.setdefault('content-length', str(len(self.body)))

        yield self.msg_start()
        yield self.msg_body(self.body)

    async def __call__(self, scope, receive, send):
        """Behave as an ASGI application."""
        async for message in self:
            await send(message)

    @property
    def body(self):
        """Create a response body."""
        if self.content is None:
            return b""

        if isinstance(self.content, bytes):
            return self.content

        return self.content.encode(self.charset)

    def msg_start(self):
        """Get ASGI response start message."""
        headers = [
            (key.lower().encode('latin-1'), str(val).encode('latin-1'))
            for key, val in self.headers.items()
        ]
        if self.cookies:
            val = self.cookies.output(header='').strip()
            headers.append((b"set-cookie", val.encode('latin-1')))

        return {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": headers,
        }

    def msg_body(self, body, /, more_body=False):
        """Get ASGI response body message."""
        return {"type": "http.response.body", "body": body, "more_body": more_body}

    def msg_end(self):
        """Get ASGI response finish message."""
        return self.msg_body(b'')


class ResponseText(Response):
    """Plain-text Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'text/plain'
        super().__init__(*args, **kwargs)


class ResponseHTML(Response):
    """HTML Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'text/html'
        super().__init__(*args, **kwargs)


class ResponseJSON(Response):
    """JSON Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'application/json'
        super().__init__(*args, **kwargs)

    @property
    def body(self):
        """Jsonify the content."""
        return dumps(self.content, ensure_ascii=False, allow_nan=False).encode(self.charset)


class ResponseRedirect(Response):
    """Redirect Response."""

    def __init__(self, url, *args, status_code=HTTPStatus.TEMPORARY_REDIRECT.value, **kwargs):
        """Set status code and prepare location."""
        if not (300 <= status_code < 400):
            raise ASGIError(f"Invalid status_code ({status_code}).")

        super(ResponseRedirect, self).__init__(*args, status_code=status_code, **kwargs)
        self.headers["location"] = quote_plus(str(url), safe=":/%#?&=@[]!$&'()*+,;")


class ResponseError(Response, Exception):
    """Raise `ErrorResponse` to stop processing and return HTTP Error Response."""

    def __init__(self, status_code=HTTPStatus.INTERNAL_SERVER_ERROR.value, content=None, **kwargs):
        """Check error status."""
        if status_code < 400:
            raise ASGIError(f"Invalid status_code ({status_code}).")
        content = content or HTTPStatus(status_code).description
        super(ResponseError, self).__init__(status_code=status_code, content=content, **kwargs)


class ResponseStream(Response):
    """Stream response."""

    def __init__(self, content, **kwargs):
        """Ensure that the content is awaitable."""
        assert isasyncgen(content), "Content have to be awaitable"
        super(ResponseStream, self).__init__(content=content, **kwargs)

    async def __aiter__(self):
        """Iterate through the response."""
        yield self.msg_start()

        async for chunk in self.content:
            if not isinstance(chunk, bytes):
                chunk = str(chunk).encode(self.charset)
            yield self.msg_body(chunk, more_body=True)

        yield self.msg_end()


class ResponseFile(Response):
    """Read and stream a file."""

    def __init__(self, filepath, chunk_size=32 * 1024, headers_only=False, **kwargs):
        """Store filepath to self."""
        filepath = Path(filepath)
        self.chunk_size = chunk_size
        self.headers_only = headers_only
        super(ResponseFile, self).__init__(content=filepath, **kwargs)
        try:
            stat = os.stat(filepath)
        except FileNotFoundError as exc:
            raise ASGIError(*exc.args)

        self.headers.setdefault('content-disposition', f'attachment; filename="{filepath.name}"')
        self.headers.setdefault('content-type', guess_type(filepath)[0] or "text/plain")
        self.headers.setdefault('content-length', str(stat.st_size))
        self.headers.setdefault('last-modified', formatdate(stat.st_mtime, usegmt=True))
        etag = str(stat.st_mtime) + "-" + str(stat.st_size)
        self.headers.setdefault('etag', md5(etag.encode()).hexdigest())

    async def __aiter__(self):
        """Iterate throug the file."""
        yield self.msg_start()
        if not self.headers_only:
            if current_async_library() == 'trio':
                async with await trio.open_file(self.content, 'rb') as fp:
                    while chunk := await fp.read(self.chunk_size):
                        yield self.msg_body(chunk, more_body=True)

            else:
                if aiofile is None:
                    raise ASGIError('`aiofile` is required to return files with asyncio')

                async with aiofile.AIOFile(self.content, mode='rb') as fp:
                    async for chunk in aiofile.Reader(fp, chunk_size=self.chunk_size):
                        yield self.msg_body(chunk, more_body=True)

        yield self.msg_end()


async def parse_response(response, headers=None) -> Response:
    """Parse the given object and convert it into a asgi_tools.Response."""

    while isawaitable(response):
        response = await response

    if isinstance(response, Response):
        return response

    if isinstance(response, (str, bytes)):
        return ResponseHTML(response, headers=headers)

    if isinstance(response, tuple):
        status, *content = response
        if len(content) > 1:
            headers, *content = content
        response = await parse_response(*(content or ['']), headers=headers)
        response.status_code = status
        return response

    if response is None or isinstance(response, (dict, list, int, bool)):
        return ResponseJSON(response, headers=headers)

    return ResponseText(str(response), headers=headers)
