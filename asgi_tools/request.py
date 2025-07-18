"""ASGI-Tools includes a `asgi_tools.Request` class that gives you a nicer interface onto the
incoming request.
"""

from __future__ import annotations

from http import cookies
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterator, Mapping, Protocol, TypeVar

from yarl import URL

from ._compat import json_loads
from .constants import DEFAULT_CHARSET
from .errors import ASGIDecodeError
from .forms import read_formdata
from .types import TJSON, TASGIReceive, TASGIScope, TASGISend
from .utils import CIMultiDict, parse_headers, parse_options_header

if TYPE_CHECKING:
    from pathlib import Path

    from multidict import MultiDict, MultiDictProxy

T = TypeVar("T")


class UploadHandler(Protocol):
    """Protocol for file upload handlers."""

    async def __call__(self, filename: str, content_type: str, content: bytes) -> str | Path: ...


class Request(TASGIScope):
    """Provides a convenient, high-level interface for incoming HTTP requests.

    :param scope: HTTP ASGI Scope
    :param receive: an asynchronous callable which lets the application
                    receive event messages from the client
    :param send: an asynchronous callable which lets the application
                    send event messages to the client

    """

    __slots__ = (
        "_body",
        "_cookies",
        "_form",
        "_headers",
        "_is_read",
        "_media",
        "_url",
        "receive",
        "scope",
        "send",
    )

    def __init__(self, scope: TASGIScope, receive: TASGIReceive, send: TASGISend):
        """Create a request based on the given scope."""
        self.scope = scope
        self.receive = receive
        self.send = send

        self._is_read: bool = False
        self._url: URL | None = None
        self._body: bytes | None = None
        self._form: MultiDict | None = None
        self._headers: CIMultiDict | None = None
        self._media: dict[str, str] | None = None
        self._cookies: dict[str, str] | None = None

    def __str__(self) -> str:
        """Return the request's params."""
        scope_type = self.scope["type"]
        if scope_type == "websocket":
            return f"{scope_type} {self.path}"

        return f"{scope_type} {self.method} {self.url.path}"

    def __repr__(self):
        """Represent the request."""
        return f"<Request {self}>"

    def __getitem__(self, key: str) -> Any:
        """Proxy the method to the scope."""
        return self.scope[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Proxy the method to the scope."""
        self.scope[key] = value

    def __delitem__(self, key: str) -> None:
        """Proxy the method to the scope."""
        del self.scope[key]

    def __iter__(self) -> Iterator[str]:
        """Proxy the method to the scope."""
        return iter(self.scope)

    def __len__(self) -> int:
        """Proxy the method to the scope."""
        return len(self.scope)

    def __getattr__(self, name: str) -> Any:
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
            host = self.headers.get("host")
            if host is None:
                if "server" in scope:
                    host, port = scope["server"]
                    if port:
                        host = f"{host}:{port}"
                else:
                    host = "localhost"

            self._url = URL.build(
                host=host,
                scheme=scope.get("scheme", "http"),
                encoded=True,
                path=f"{ scope.get('root_path', '') }{ scope['path'] }",
                query_string=scope["query_string"].decode(encoding="ascii"),
            )

        return self._url

    @property
    def headers(self) -> CIMultiDict:
        """A lazy property that parses the current scope's headers, decodes them as strings and
        returns case-insensitive multi-dict :py:class:`multidict.CIMultiDict`.

        .. code-block:: python

            request = Request(scope)

            assert request.headers['content-type']
            assert request.headers['authorization']

        See :py:mod:`multidict` documentation for futher reference.

        """
        if self._headers is None:
            self._headers = parse_headers(self.scope["headers"])
        return self._headers

    @property
    def cookies(self) -> dict[str, str]:
        """A lazy property that parses the current scope's cookies and returns a dictionary.

        .. code-block:: python

            request = Request(scope)
            ses = request.cookies.get('session')

        """
        if self._cookies is None:
            self._cookies = {}
            cookie = self.headers.get("cookie")
            if cookie:
                for chunk in cookie.split(";"):
                    key, _, val = chunk.partition("=")
                    self._cookies[key.strip()] = cookies._unquote(val.strip())

        return self._cookies

    @property
    def media(self) -> Mapping[str, str]:
        """Prepare a media data for the request."""
        if self._media is None:
            content_type_header = self.headers.get("content-type", "")
            content_type, opts = parse_options_header(content_type_header)
            self._media = dict(opts, content_type=content_type)

        return self._media

    @property
    def charset(self) -> str:
        """Get an encoding charset for the current scope."""
        return self.media.get("charset", DEFAULT_CHARSET)

    @property
    def query(self) -> MultiDictProxy[str]:
        """A lazy property that parse the current query string and returns it as a
        :py:class:`multidict.MultiDict`.

        """
        return self.url.query

    @property
    def content_type(self) -> str:
        """Get a content type for the current scope."""
        return self.media["content_type"]

    async def stream(self) -> AsyncGenerator:
        """Stream the request's body.

        The method provides byte chunks without storing the entire body to memory.
        Any subsequent calls to :py:meth:`body`, :py:meth:`form`, :py:meth:`json`
        or :py:meth:`data` will raise an error.

        .. warning::
            You can only read stream once. Second call raises an error. Save a readed stream into a
            variable if you need.

        """
        if self._is_read:
            if self._body is None:
                raise RuntimeError("Stream has been read")
            yield self._body

        else:
            self._is_read = True
            while True:
                message = await self.receive()
                yield message.get("body", b"")
                if not message.get("more_body"):
                    break

    async def body(self) -> bytes:
        """Read and return the request's body as bytes.

        `body = await request.body()`
        """
        if self._body is None:
            data = bytearray()
            async for chunk in self.stream():
                data.extend(chunk)
            self._body = bytes(data)

        return self._body

    async def text(self) -> str:
        """Read and return the request's body as a string.

        `text = await request.text()`
        """
        body = await self.body()
        try:
            return body.decode(self.charset or DEFAULT_CHARSET)
        except (LookupError, ValueError) as exc:
            raise ASGIDecodeError from exc

    async def json(self) -> TJSON:
        """Read and return the request's body as a JSON.

        `json = await request.json()`

        """
        try:
            return json_loads(await self.body())
        except (LookupError, ValueError) as exc:
            raise ASGIDecodeError from exc

    async def form(
        self,
        max_size: int = 0,
        upload_to: UploadHandler | None = None,
        file_memory_limit: int = 1024 * 1024,
    ) -> MultiDict:
        """Read and return the request's form data.

        :param max_size: Maximum size of the form data in bytes
        :type max_size: int
        :param upload_to: Callable to handle file uploads
        :type upload_to: Optional[UploadHandler]
        :param file_memory_limit: Maximum size of file to keep in memory
        :type file_memory_limit: int
        :return: Form data as MultiDict
        :rtype: MultiDict

        `formdata = await request.form()`
        """
        if self._form is None:
            self._form = await read_formdata(
                self,
                max_size=max_size,
                upload_to=upload_to,
                file_memory_limit=file_memory_limit,
            )
        return self._form

    async def data(self, *, raise_errors: bool = False) -> str | bytes | MultiDict | TJSON:
        """Read and return the request's data based on content type.

        :param raise_errors: Raise an error if the given data is invalid.
        :return: Request data in appropriate format
        :rtype: Union[str, bytes, MultiDict, TJSON]
        :raises ASGIDecodeError: If data cannot be decoded and raise_errors is True

        `data = await request.data()`

        If `raise_errors` is false (by default) and the given data is invalid (ex. invalid json)
        the request's body would be returned.

        Returns data from :py:meth:`json` for `application/json`, :py:meth:`form` for
        `application/x-www-form-urlencoded`,  `multipart/form-data` and :py:meth:`text` otherwise.
        """
        content_type = self.content_type
        try:
            if content_type in {
                "multipart/form-data",
                "application/x-www-form-urlencoded",
            }:
                return await self.form()

            if content_type == "application/json":
                return await self.json()

        except ASGIDecodeError:
            if raise_errors:
                raise
            return await self.body()

        if content_type.startswith("text/"):
            return await self.text()

        return await self.body()
