""" ASGI-Tools includes a `asgi_tools.Request` class that gives you a nicer interface onto the
incoming request.
"""

import typing as t
from cgi import parse_header, FieldStorage
from functools import wraps
from http import cookies
from io import BytesIO
from json import loads
from urllib.parse import parse_qsl

from multidict import MultiDict
from yarl import URL

from . import ASGIDecodeError, DEFAULT_CHARSET
from ._compat import cached_property, TypedDict
from ._types import Scope, Receive, Send, JSONType
from .utils import parse_headers, CIMultiDict


def process_decode(message: str):
    """Handle errors."""

    def decorator(amethod):

        @wraps(amethod)
        async def wrapper(self, *args, **kwargs):
            try:
                return await amethod(self, *args, **kwargs)
            except (LookupError, ValueError):
                raise ASGIDecodeError(message)

        return wrapper
    return decorator


class Media(TypedDict):
    """Keep requests media data."""

    opts: t.Dict[str, str]
    content_type: str


class Request(dict):
    """Represent a HTTP Request.

    :param scope: HTTP ASGI Scope
    :param receive: an asynchronous callable which lets the application
                    receive event messages from the client

    """

    method: str  #: Contains the request's HTTP method

    def __init__(self, scope: Scope, receive: Receive = None, send: Send = None) -> None:
        """Create a request based on the given scope."""
        super(Request, self).__init__(scope)
        self._body: t.Optional[bytes] = None
        self._receive: t.Optional[Receive] = receive
        self._send: t.Optional[Send] = send

    def __getattr__(self, name: str) -> t.Any:
        """Proxy the request's unknown attributes to scope."""
        return self[name]

    @cached_property
    def url(self) -> URL:
        """A lazy property that parses the current URL and returns :class:`yarl.URL` object.

        .. code-block:: python

            request = Request(scope)
            assert str(request.url) == '... the full http URL ..'
            assert request.url.scheme
            assert request.url.host
            assert request.url.query is not None
            assert request.url.query_string is not None

        See :py:mod:`yarl` documentation for further reference.

        """
        host, port = self.get('server') or (None, None)
        host = self.headers.get('host') or host or ''
        host, _, _ = host.partition(':')
        return URL.build(
            scheme=self.get('scheme', 'http'), host=host, port=port, encoded=True,
            path=f"{ self.get('root_path', '') }{ self['path'] }",
            query_string=self.get("query_string", b"").decode("latin-1"),
        )

    @cached_property
    def headers(self) -> CIMultiDict:
        """ A lazy property that parses the current scope's headers, decodes them as strings and
        returns case-insensitive multi-dict :py:class:`multidict.CIMultiDict`.

        .. code-block:: python

            request = Request(scope)

            assert request.headers['content-type']
            assert request.headers['authorization']

        See :py:mod:`multidict` documentation for futher reference.

        """
        return parse_headers(self.get('headers') or [])

    @cached_property
    def cookies(self) -> t.Dict[str, str]:
        """A lazy property that parses the current scope's cookies and returns a dictionary.

        .. code-block:: python

            request = Request(scope)
            ses = request.cookies.get('session')

        """
        data = {}
        cookie = self.headers.get('cookie')
        if cookie:
            for chunk in cookie.split(';'):
                key, _, val = chunk.partition('=')
                data[key.strip()] = cookies._unquote(val.strip())  # type: ignore

        return data

    @cached_property
    def media(self) -> Media:
        """Prepare a media data for the request."""
        content_type, opts = parse_header(self.headers.get('content-type', ''))
        return Media(opts=opts, content_type=content_type)

    @property
    def charset(self) -> str:
        """Get an encoding charset for the current scope."""
        return self.media['opts'].get('charset', DEFAULT_CHARSET)

    @property
    def content_type(self) -> str:
        """Get a content type for the current scope."""
        return self.media['content_type']

    async def stream(self) -> t.AsyncGenerator:
        """Stream the request's body."""
        if not self._receive:
            raise RuntimeError('Request doesnt have a receive coroutine')

        message = await self._receive()
        yield message.get('body', b'')
        while message.get('more_body'):
            message = await self._receive()
            yield message.get('body', b'')

    async def body(self) -> bytes:
        """Read and return the request's body as bytes.

        `body = await request.body()`
        """
        if self._body is None:
            chunks = []
            async for chunk in self.stream():
                chunks.append(chunk)

            self._body = b"".join(chunks)

        return self._body

    @process_decode(message='Invalid Encoding')
    async def text(self) -> str:
        """Read and return the request's body as a string.

        `text = await request.text()`
        """
        body = await self.body()
        charset = self.charset or DEFAULT_CHARSET
        return body.decode(charset)

    @process_decode(message='Invalid JSON')
    async def json(self) -> JSONType:
        """Read and return the request's body as a JSON.

        `json = await request.json()`
        """
        text = await self.text()
        return loads(text)

    @process_decode(message='Invalid Form Data')
    async def form(self) -> MultiDict:
        """Read and return the request's multipart formdata as a multidict.

        `formdata = await request.form()`
        """
        form: MultiDict = MultiDict()
        body = await self.body()

        # TODO: Improve multipart parsing
        if self.content_type == 'multipart/form-data':
            fs = FieldStorage(
                BytesIO(body), headers=self.headers, encoding=self.charset,
                environ={'REQUEST_METHOD': self.method})
            for name in fs:
                for val in fs.getlist(name):
                    form[name] = val

            return form

        query = body.decode(self.charset)
        form.extend(parse_qsl(qs=query, keep_blank_values=True, encoding=self.charset))

        return form

    def data(self) -> t.Awaitable[t.Union[str, JSONType, MultiDict]]:
        """The method checks `request.content_type` and parse the request's body automatically.

        `data = await request.data()`

        Returns JSON for `application/json`, formdata for forms and text otherwise.
        """
        if self.content_type in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
            return self.form()

        if self.content_type == 'application/json':
            return self.json()

        return self.text()
