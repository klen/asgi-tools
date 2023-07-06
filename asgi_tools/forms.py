"""Work with multipart."""
from __future__ import annotations

from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING, Callable, Dict, Optional
from urllib.parse import unquote_to_bytes

from multidict import MultiDict

from .multipart import BaseParser, MultipartParser, QueryStringParser
from .utils import parse_options_header

if TYPE_CHECKING:
    from asgi_tools.request import Request


async def read_formdata(
    request: "Request",
    max_size: int,
    upload_to: Optional[Callable],
    file_memory_limit: int = 1024 * 1024,
) -> MultiDict:
    """Read formdata from the given request."""
    if request.content_type == "multipart/form-data":
        reader: FormReader = MultipartReader(
            request.charset,
            upload_to,
            file_memory_limit,
        )
    else:
        reader = FormReader(request.charset)

    parser = reader.init_parser(request, max_size)
    async for chunk in request.stream():
        parser.write(chunk)

    parser.finalize()
    return reader.form


class FormReader:
    """Process querystring form data."""

    __slots__ = "form", "curname", "curvalue", "charset"

    def __init__(self, charset: str):
        self.charset = charset
        self.curname = bytearray()
        self.curvalue = bytearray()
        self.form: MultiDict = MultiDict()

    def init_parser(self, _: "Request", max_size: int) -> BaseParser:
        return QueryStringParser(
            {
                "field_name": self.on_field_name,
                "field_data": self.on_field_data,
                "field_end": self.on_field_end,
            },
            max_size=max_size,
        )

    def on_field_name(self, data: bytes, start: int, end: int):
        self.curname += data[start:end]

    def on_field_data(self, data: bytes, start: int, end: int):
        self.curvalue += data[start:end]

    def on_field_end(self, *_):
        self.form.add(
            unquote_plus(self.curname).decode(self.charset),
            unquote_plus(self.curvalue).decode(self.charset),
        )
        self.curname.clear()
        self.curvalue.clear()


class MultipartReader(FormReader):
    """Process multipart formdata."""

    __slots__ = (
        "form",
        "curname",
        "curvalue",
        "charset",
        "name",
        "partdata",
        "headers",
        "upload_to",
        "file_memory_limit",
    )

    def __init__(self, charset: str, upload_to: Optional[Callable], file_memory_limit: int):
        super().__init__(charset)
        self.name = ""
        self.headers: Dict[bytes, bytes] = {}
        self.partdata = BytesIO()
        self.upload_to = upload_to
        self.file_memory_limit = file_memory_limit

    def init_parser(self, request: "Request", max_size: int) -> BaseParser:
        boundary = request.media.get("boundary", "")
        if not boundary:
            raise ValueError("Invalid content type boundary")  # noqa:

        return MultipartParser(
            boundary,
            {
                "header_end": self.on_header_end,
                "header_field": self.on_header_field,
                "headers_finished": self.on_headers_finished,
                "header_value": self.on_header_value,
                "part_data": self.on_part_data,
                "part_end": self.on_part_end,
            },
            max_size=max_size,
        )

    def on_header_field(self, data: bytes, start: int, end: int):
        self.curname += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int):
        self.curvalue += data[start:end]

    def on_header_end(self, *_):
        self.headers[bytes(self.curname.lower())] = bytes(self.curvalue)
        self.curname.clear()
        self.curvalue.clear()

    def on_headers_finished(self, *_):
        _, options = parse_options_header(
            self.headers[b"content-disposition"].decode(self.charset),
        )
        self.name = options["name"]
        if "filename" in options:
            upload_to = self.upload_to
            if upload_to is not None:
                filename = upload_to(options["filename"])
                self.partdata = f = open(filename, "wb+")  # noqa: SIM

            else:
                self.partdata = f = SpooledTemporaryFile(self.file_memory_limit)
                f._file.name = options["filename"]  # type: ignore[]

            f.content_type = self.headers[b"content-type"].decode(self.charset)

    def on_part_data(self, data: bytes, start: int, end: int):
        self.partdata.write(data[start:end])

    def on_part_end(self, *_):
        field_data = self.partdata
        if isinstance(field_data, BytesIO):
            self.form.add(self.name, field_data.getvalue().decode(self.charset))

        else:
            field_data.seek(0)
            self.form.add(self.name, field_data)

        self.partdata = BytesIO()
        self.headers = {}


def unquote_plus(value: bytearray) -> bytes:
    value = value.replace(b"+", b" ")
    return unquote_to_bytes(bytes(value))
