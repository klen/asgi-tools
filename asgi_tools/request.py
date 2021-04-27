""" ASGI-Tools includes a `asgi_tools.Request` class that gives you a nicer interface onto the
incoming request.
"""

import typing as t
from cgi import parse_header
from http import cookies

from multidict import MultiDict
from yarl import URL

from . import ASGIDecodeError, DEFAULT_CHARSET
from ._compat import json_loads
from .typing import Scope, Receive, Send, JSONType
from .utils import parse_headers, CIMultiDict


class Request(dict):
    """Represent a HTTP Request.

    :param scope: HTTP ASGI Scope
    :param receive: an asynchronous callable which lets the application
                    receive event messages from the client

    """

    _is_read: bool = False
    _url: t.Optional[URL] = None
    _body: t.Optional[bytes] = None
    _form: t.Optional[MultiDict] = None
    _headers: t.Optional[CIMultiDict] = None
    _media: t.Optional[t.Dict[str, str]] = None
    _cookies: t.Optional[t.Dict[str, str]] = None

    def __init__(self, scope: Scope, receive: Receive = None, send: Send = None) -> None:
        """Create a request based on the given scope."""
        super(Request, self).__init__(scope)
        self._receive = receive
        self._send = send

    def __getattr__(self, name: str) -> t.Any:
        """Proxy the request's unknown attributes to scope."""
        return self[name]

    @property
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
        if self._url is None:
            host, port = self.get('server') or (None, None)
            host = self.headers.get('host') or host or ''
            host, _, _ = host.partition(':')
            self._url = URL.build(
                scheme=self.get('scheme', 'http'), host=host, port=port, encoded=True,
                path=f"{ self.get('root_path', '') }{ self['path'] }",
                query_string=self.get("query_string", b"").decode("latin-1"),
            )

        return self._url

    @property
    def headers(self) -> CIMultiDict:
        """ A lazy property that parses the current scope's headers, decodes them as strings and
        returns case-insensitive multi-dict :py:class:`multidict.CIMultiDict`.

        .. code-block:: python

            request = Request(scope)

            assert request.headers['content-type']
            assert request.headers['authorization']

        See :py:mod:`multidict` documentation for futher reference.

        """
        if self._headers is None:
            self._headers = parse_headers(self['headers'])
        return self._headers

    @property
    def cookies(self) -> t.Dict[str, str]:
        """A lazy property that parses the current scope's cookies and returns a dictionary.

        .. code-block:: python

            request = Request(scope)
            ses = request.cookies.get('session')

        """
        if self._cookies is None:
            self._cookies = {}
            cookie = self.headers.get('cookie')
            if cookie:
                for chunk in cookie.split(';'):
                    key, _, val = chunk.partition('=')
                    self._cookies[key.strip()] = cookies._unquote(val.strip())  # type: ignore

        return self._cookies

    @property
    def media(self) -> t.Dict[str, str]:
        """Prepare a media data for the request."""
        if self._media is None:
            content_type, opts = parse_header(self.headers.get('content-type', ''))
            self._media = dict(opts, content_type=content_type)

        return self._media

    @property
    def charset(self) -> str:
        """Get an encoding charset for the current scope."""
        return self.media.get('charset', DEFAULT_CHARSET)

    @property
    def content_type(self) -> str:
        """Get a content type for the current scope."""
        return self.media['content_type']

    async def stream(self) -> t.AsyncGenerator:
        """Stream the request's body.

        The method provides byte chunks without storing the entire body to memory.
        Any subsequent calls to :py:meth:`body`, :py:meth:`form`, :py:meth:`json`
        or :py:meth:`data` will raise an error.

        .. warning::
            You can only read stream once. Second call raises an error. Save a readed stream into a
            variable if you need.

        """
        if not self._receive:
            raise RuntimeError('Request doesnt have a receive coroutine')

        if self._is_read:
            raise RuntimeError('Stream has been read')

        self._is_read = True
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

    async def text(self) -> str:
        """Read and return the request's body as a string.

        `text = await request.text()`
        """
        body = await self.body()
        try:
            return body.decode(self.charset or DEFAULT_CHARSET)
        except (LookupError, ValueError):
            raise ASGIDecodeError('Invalid Encoding')

    async def json(self) -> JSONType:
        """Read and return the request's body as a JSON.

        `json = await request.json()`

        """
        try:
            return json_loads(await self.body())
        except (LookupError, ValueError):
            raise ASGIDecodeError('Invalid Encoding')

    async def form(self, max_size: int = 0, upload_to: t.Callable = None,
                   file_memory_limit: int = 1024 * 1024) -> MultiDict:
        """Read and return the request's multipart formdata as a multidict.

        The method reads the request's stream stright into memory formdata.
        Any subsequent calls to :py:meth:`body`, :py:meth:`json` will raise an error.

        `formdata = await request.form()`

        """
        from .forms import read_formdata

        if self._form is None:
            try:
                self._form = await read_formdata(self, max_size, upload_to, file_memory_limit)
            except (LookupError, ValueError):
                raise ASGIDecodeError('Invalid Encoding')

        return self._form

    def data(self) -> t.Awaitable[t.Union[str, JSONType, MultiDict]]:
        """The method checks Content-Type Header and parse the request's data automatically.

        `data = await request.data()`

        Returns data from :py:meth:`json` for `application/json`, :py:meth:`form` for
        `application/x-www-form-urlencoded`,  `multipart/form-data` and :py:meth:`text` otherwise.
        """
        if self.content_type in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
            return self.form()

        if self.content_type == 'application/json':
            return self.json()

        return self.text()
