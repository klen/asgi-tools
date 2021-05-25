"""ASGI-Tools includes a `asgi_tools.Request` class that gives you a nicer interface onto the
incoming request.
"""

from __future__ import annotations

import typing as t
from cgi import parse_header
from http import cookies

from multidict import MultiDict
from yarl import URL

from . import ASGIDecodeError, DEFAULT_CHARSET
from ._compat import json_loads
from .typing import Scope, Receive, Send, JSONType
from .utils import parse_headers, CIMultiDict


class Request(t.MutableMapping):
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
        self.scope = scope
        self.receive = receive
        self.send = send

    def __repr__(self):
        """Represent the request."""
        return f"<Request {self.content_type} {self.method} {self.url.path}>"

    def __getitem__(self, key: str) -> t.Any:
        """Proxy the method to the scope."""
        return self.scope[key]

    def __setitem__(self, key: str, value: t.Any) -> None:
        """Proxy the method to the scope."""
        self.scope[key] = value

    def __delitem__(self, key: str) -> None:
        """Proxy the method to the scope."""
        del self.scope[key]

    def __iter__(self) -> t.Iterator[str]:
        """Proxy the method to the scope."""
        return iter(self.scope)

    def __len__(self) -> int:
        """Proxy the method to the scope."""
        return len(self.scope)

    def __getattr__(self, name: str) -> t.Any:
        """Proxy the request's unknown attributes to scope."""
        return self.scope[name]

    def __copy__(self, **mutations) -> Request:
        """Copy the request to a new one."""
        return Request(dict(self.scope, **mutations), self.receive, self.send)

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
            scope = self.scope
            host = self.headers.get('host')
            if host is None and ('server' in scope):
                host, port = scope['server']
                if port:
                    host = f"{host}:{port}"

            self._url = URL.build(
                host=host,  # type: ignore
                scheme=scope.get('scheme', 'http'),
                encoded=True, path=f"{ scope.get('root_path', '') }{ scope['path'] }",
                query_string=scope['query_string'].decode("latin-1"),
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
            self._headers = parse_headers(self.scope['headers'])
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
    def query(self) -> MultiDict:
        """A lazy property that parse the current query string and returns it as a
        :py:class:`multidict.MultiDict`.

        """
        return self.url.query

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
        if not self.receive:
            raise RuntimeError('Request doesnt have a receive coroutine')

        if self._is_read:
            raise RuntimeError('Stream has been read')

        self._is_read = True
        message = await self.receive()
        yield message.get('body', b'')
        while message.get('more_body'):
            message = await self.receive()
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
            raise ASGIDecodeError('Invalid JSON')

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

    async def data(self, raise_errors: bool = False) -> t.Union[str, bytes, JSONType, MultiDict]:
        """The method checks Content-Type Header and parse the request's data automatically.

        `data = await request.data()`

        If `raise_errors` is false (by default) and the given data is invalid (ex. invalid json)
        the request's body would be returned.

        Returns data from :py:meth:`json` for `application/json`, :py:meth:`form` for
        `application/x-www-form-urlencoded`,  `multipart/form-data` and :py:meth:`text` otherwise.
        """
        try:
            if self.content_type in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
                return await self.form()

            if self.content_type == 'application/json':
                return await self.json()

            return await self.text()

        except ASGIDecodeError:
            if raise_errors:
                raise
            return await self.body()
