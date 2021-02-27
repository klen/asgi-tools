"""Work with multipart."""

from __future__ import annotations

import abc
import typing as t
from cgi import parse_header
from tempfile import SpooledTemporaryFile
from urllib.parse import unquote_plus

from multidict import MultiDict
from multipart import QuerystringParser as _FormParser, MultipartParser as _MultipartParser

from .request import Request


# Messages
START = 1
END = 2
FIELD_START = 10
FIELD_NAME = 11
FIELD_DATA = 12
FIELD_END = 13
PART_BEGIN = 20
PART_DATA = 21
PART_END = 22
HEADER_FIELD = 30
HEADER_VALUE = 31
HEADER_END = 32
HEADERS_FINISHED = 33


class ParserMeta(abc.ABCMeta):
    """Prepare a parser."""

    def __new__(mcs, name, bases, params):
        """Detect callbacks."""
        cls = super(ParserMeta, mcs).__new__(mcs, name, bases, params)
        cls.callbacks = {m for m in cls.__dict__ if m.startswith('on_')}
        return cls


class Parser(metaclass=ParserMeta):
    """Base abstract parser class."""

    __slots__ = 'messages',

    callbacks: t.Dict = {}

    def __init__(self):
        """Store a stream."""
        self.messages = []

    @abc.abstractmethod
    async def parse(self, request: Request, **opts) -> MultiDict:
        """Parse data."""
        pass


class FormParser(Parser):
    """Parse querystring form data."""

    async def parse(self, request: Request,
                    max_size: t.Union[int, float] = float('inf'), **opts) -> MultiDict:
        """Parse data."""
        parser = _FormParser(
            {m: getattr(self, m) for m in self.callbacks}, max_size=max_size)
        async for chunk in request.stream():
            parser.write(chunk)

        parser.finalize()

        items: t.List[t.Tuple[str, str]] = []
        name, value = b'', b''
        for event, data in self.messages:
            if event == FIELD_START:
                name, value = b'', b''

            elif event == FIELD_NAME:
                name += data

            elif event == FIELD_DATA:
                value += data

            elif event == FIELD_END:
                items.append((
                    unquote_plus(name.decode("latin-1")),
                    unquote_plus(value.decode("latin-1"))
                ))

        return MultiDict(items)

    def on_field_start(self):
        self.messages.append((FIELD_START, b""))

    def on_field_end(self):
        self.messages.append((FIELD_END, b""))

    def on_field_name(self, data: bytes, start: int, end: int):
        self.messages.append((FIELD_NAME, data[start:end]))

    def on_field_data(self, data: bytes, start: int, end: int):
        self.messages.append((FIELD_DATA, data[start:end]))


class MultipartParser(Parser):
    """Parse multipart formdata."""

    async def parse(self, request: Request, max_size: t.Union[int, float] = float('inf'),  # noqa
                    upload_to: str = None, file_memory_limit: int = 1024 * 1024,
                    **opts) -> MultiDict:
        """Parse data."""

        _, params = parse_header(request.headers["content-type"])
        boundary = params.get('boundary')
        charset = params.get('charset', request.charset)
        parser = _MultipartParser(
            boundary, {m: getattr(self, m) for m in self.callbacks}, max_size=max_size)
        async for chunk in request.stream():
            parser.write(chunk)

        parser.finalize()

        items: t.List[t.Tuple[str, t.Union[str, t.IO]]] = []
        headers, data = {}, b''
        header_name, header_value = b'', b''
        name, value = '', b''
        fileobj: t.Optional[t.IO] = None
        for event, data in self.messages:
            if event == HEADER_FIELD:
                header_name += data
            elif event == HEADER_VALUE:
                header_value += data
            elif event == HEADER_END:
                headers[header_name.lower()] = header_value
                header_name, header_value = b'', b''
            elif event == HEADERS_FINISHED:
                disposition, options = parse_header(
                    headers[b'content-disposition'].decode(charset))
                name = options['name']
                if 'filename' in options:
                    fileobj = open(upload_to, 'a') if upload_to else SpooledTemporaryFile(
                        file_memory_limit)
                    fileobj.filename = options['filename']  # type: ignore
                    fileobj.content_type = headers[b'content-type'].decode(charset)  # type: ignore
            elif event == PART_BEGIN:
                headers, data = {}, b''
            elif event == PART_DATA:
                if fileobj is None:
                    value += data
                else:
                    fileobj.write(data)
            elif event == PART_END:
                if fileobj is None:
                    items.append((name, data.decode('charset')))
                else:
                    fileobj.seek(0)
                    items.append((name, fileobj))

                value, fileobj = b'', None

        return MultiDict(items)

    def on_part_begin(self):
        self.messages.append((PART_BEGIN, b""))

    def on_part_data(self, data: bytes, start: int, end: int):
        self.messages.append((PART_DATA, data[start:end]))

    def on_part_end(self):
        self.messages.append((PART_END, b""))

    def on_header_field(self, data: bytes, start: int, end: int):
        self.messages.append((HEADER_FIELD, data[start:end]))

    def on_header_value(self, data: bytes, start: int, end: int):
        self.messages.append((HEADER_VALUE, data[start:end]))

    def on_header_end(self):
        self.messages.append((HEADER_END, b""))

    def on_headers_finished(self):
        self.messages.append((HEADERS_FINISHED, b""))

# pylama: ignore=D
