"""ASGI responses."""

from inspect import isawaitable, isasyncgen
from http import cookies, HTTPStatus
from json import dumps
from urllib.parse import quote_plus

from multidict import CIMultiDict

from . import DEFAULT_CHARSET


# TODO: File response


async def parse_response(response):
    """Parse the given object and convert it into a asgi_tools.Response."""

    while isawaitable(response):
        response = await response

    if isinstance(response, Response):
        return response

    if isinstance(response, (str, bytes)):
        return HTMLResponse(response)

    if isinstance(response, tuple):
        status, *response = response
        response = await parse_response(*(response or ['']))
        response.status_code = status
        return response

    if isinstance(response, (dict, list, int, bool)):
        return JSONResponse(response)

    return PlainTextResponse(str(response))


class Response:
    """ASGI Response."""

    charset = DEFAULT_CHARSET

    def __init__(
            self, content=None, status_code=HTTPStatus.OK.value, headers=None, content_type=None):
        """Setup the response."""
        self.content = content
        self.status_code = status_code
        self._headers = CIMultiDict(headers or {})
        self.cookies = cookies.SimpleCookie()
        if content_type:
            if content_type.startswith('text/'):
                content_type = f"{content_type}; charset={self.charset}"

            self._headers['content-type'] = content_type

    def __str__(self):
        """Stringify the response."""
        return f"{self.status_code}"

    def __repr__(self):
        """Stringify the response."""
        return f"<Response '{ self }'"

    async def __aiter__(self):
        """Iterate self through ASGI messages."""
        headers = self.get_headers()
        if 'content-length' not in self._headers:
            headers.append((b'content-length', str(len(self.body)).encode()))

        yield {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": headers,
        }
        yield {"type": "http.response.body", "body": self.body}

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

    def get_headers(self):
        """Render the response's headers."""
        headers = [
            (key.lower().encode('latin-1'), val.encode('latin-1'))
            for key, val in self._headers.items()
        ]
        if self.cookies:
            val = self.cookies.output(header='').strip()
            headers.append((b"set-cookie", val.encode('latin-1')))
        return headers


class HTMLResponse(Response):
    """HTML Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'text/html'
        super().__init__(*args, **kwargs)


class PlainTextResponse(Response):
    """Plain-text Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'text/plain'
        super().__init__(*args, **kwargs)


class JSONResponse(Response):
    """JSON Response."""

    def __init__(self, *args, **kwargs):
        """Setup the response."""
        kwargs['content_type'] = 'application/json'
        super().__init__(*args, **kwargs)

    @property
    def body(self):
        """Jsonify the content."""
        return dumps(self.content, ensure_ascii=False, allow_nan=False).encode(self.charset)


class RedirectResponse(Response):
    """Redirect Response."""

    def __init__(self, url, *args, status_code=HTTPStatus.TEMPORARY_REDIRECT.value, **kwargs):
        """Set status code and prepare location."""
        super(RedirectResponse, self).__init__(*args, status_code=status_code, **kwargs)
        self._headers["location"] = quote_plus(str(url), safe=":/%#?&=@[]!$&'()*+,;")


class StreamResponse(Response):
    """Stream response."""

    def __init__(self, content=None, **kwargs):
        """Ensure that the content is awaitable."""
        assert isasyncgen(content), "Content have to be awaitable"
        super(StreamResponse, self).__init__(content=content, **kwargs)

    async def __aiter__(self):
        """Iterate through the response."""
        yield {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.get_headers(),
        }
        async for chunk in self.content:
            if not isinstance(chunk, bytes):
                chunk = str(chunk).encode(self.charset)
            yield {"type": "http.response.body", "body": chunk, "more_body": True}

        yield {"type": "http.response.body", "body": b"", "more_body": False}
