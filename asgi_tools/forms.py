"""Work with multipart."""

from __future__ import annotations

import io
import typing as t
from pathlib import Path
from cgi import parse_header
from tempfile import SpooledTemporaryFile
from urllib.parse import unquote_plus

from multidict import MultiDict
from multipart import QuerystringParser as _FormParser, MultipartParser as _MultipartParser

from .request import Request


class FormField:

    __slots__ = 'name', 'data'

    def __init__(self):
        self.name = b''
        self.data = b''

    def render(self) -> t.Tuple[str, str]:
        return (
            unquote_plus(self.name.decode("latin-1")),
            unquote_plus(self.data.decode("latin-1"))
        )


class FormPart:

    __slots__ = 'name', 'data', 'headers', 'header_field', 'header_value'

    def __init__(self):
        self.name = ''
        self.data = io.BytesIO()
        self.headers = {}
        self.header_field = b''
        self.header_value = b''

    def on_header_end(self):
        self.headers[self.header_field.lower()] = self.header_value
        self.header_field, self.header_value = b'', b''

    def on_headers_finished(self, upload_to: t.Union[str, Path], file_memory_limit: int):
        disposition, options = parse_header(
            self.headers[b'content-disposition'].decode('utf-8'))
        self.name = options['name']
        if 'filename' in options:
            if upload_to:
                upload_to = Path(upload_to) / options['filename']
                self.data = open(upload_to, 'wb+')

            else:
                self.data = SpooledTemporaryFile(file_memory_limit)

            self.data.filename = options['filename']  # type: ignore
            self.data.content_type = self.headers[b'content-type'].decode('utf-8')  # type: ignore

    def render(self) -> t.Tuple:
        data = self.data
        if isinstance(data, io.BytesIO):
            return self.name, data.getvalue().decode('utf-8')

        data.seek(0)
        return self.name, data


class FormParser:
    """Parse querystring form data."""

    __slots__ = 'field', 'items'

    async def parse(self, request: Request,
                    max_size: t.Union[int, float] = float('inf'), **opts) -> MultiDict:
        """Parse data."""
        self.field = FormField()
        self.items: t.List[t.Tuple[str, str]] = []

        parser = _FormParser({
            'on_field_name': self.on_field_name, 'on_field_data': self.on_field_data,
            'on_field_end': self.on_field_end}, max_size=max_size)
        async for chunk in request.stream():
            parser.write(chunk)

        parser.finalize()
        return MultiDict(self.items)

    def on_field_name(self, data: bytes, start: int, end: int):
        self.field.name += data[start:end]

    def on_field_data(self, data: bytes, start: int, end: int):
        self.field.data += data[start:end]

    def on_field_end(self):
        self.items.append(self.field.render())
        self.field = FormField()


class MultipartParser:
    """Parse multipart formdata."""

    __slots__ = 'upload_to', 'file_memory_limit', 'items', 'part'

    async def parse(self, request: Request, max_size: t.Union[int, float] = float('inf'),  # noqa
                    upload_to: t.Union[str, Path] = None, file_memory_limit: int = 1024 * 1024,
                    **opts) -> MultiDict:
        """Parse data."""

        _, params = parse_header(request.headers["content-type"])
        self.upload_to = upload_to
        self.file_memory_limit = file_memory_limit
        self.items: t.List[t.Tuple[str, t.Union[str, io.TextIOBase]]] = []
        self.part = FormPart()
        parser = _MultipartParser(params.get('boundary'), {
            'on_header_end': self.on_header_end,
            'on_header_field': self.on_header_field,
            'on_headers_finished': self.on_headers_finished,
            'on_header_value': self.on_header_value,
            'on_part_data': self.on_part_data,
            'on_part_end': self.on_part_end,
        }, max_size=max_size)
        async for chunk in request.stream():
            parser.write(chunk)

        parser.finalize()

        return MultiDict(self.items)

    def on_header_field(self, data: bytes, start: int, end: int):
        self.part.header_field += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int):
        self.part.header_value += data[start:end]

    def on_header_end(self):
        self.part.on_header_end()

    def on_headers_finished(self):
        self.part.on_headers_finished(self.upload_to, self.file_memory_limit)

    def on_part_data(self, data: bytes, start: int, end: int):
        self.part.data.write(data[start:end])

    def on_part_end(self):
        self.items.append(self.part.render())
        self.part = FormPart()


# Events
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

# pylama: ignore=D
