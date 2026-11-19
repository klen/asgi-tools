# Copyright (c) 2020 Kirill Klenov

"""Work with multipart."""

from __future__ import annotations

from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote_to_bytes

from multidict import MultiDict

from .multipart import BaseParser, MultipartParser, QueryStringParser
from .utils import parse_options_header

if TYPE_CHECKING:
    from asgi_tools.request import Request, UploadHandler


async def read_formdata(
    request: "Request",
    max_size: int,
    upload_to: "UploadHandler | None",
) -> MultiDict[Any]:
    """Read formdata from the given request."""
    if request.content_type == "multipart/form-data":
        reader: FormReader = MultipartReader(request.charset, upload_to, max_size)
    else:
        reader = FormReader(request.charset)

    parser = reader.init_parser(request, max_size)
    async for chunk in request.stream():
        parser.write(chunk)

    parser.finalize()
    return reader.form


class FormReader:
    """Process querystring form data."""

    __slots__ = "charset", "curname", "curvalue", "form"

    def __init__(self, charset: str):
        self.charset = charset
        self.curname = bytearray()
        self.curvalue = bytearray()
        self.form: MultiDict[Any] = MultiDict()

    def init_parser(
        self,
        request: "Request",  # noqa: ARG002
        max_size: int,
    ) -> BaseParser:
        return QueryStringParser(
            {
                "field_name": self.on_field_name,
                "field_data": self.on_field_data,
                "field_end": self.on_field_end,
            },
            max_size=max_size,
        )

    def on_field_name(self, data: bytes, start: int, end: int) -> None:
        self.curname += data[start:end]

    def on_field_data(self, data: bytes, start: int, end: int) -> None:
        self.curvalue += data[start:end]

    def on_field_end(self, *_: Any) -> None:
        self.form.add(
            unquote_plus(self.curname).decode(self.charset),
            unquote_plus(self.curvalue).decode(self.charset),
        )
        self.curname.clear()
        self.curvalue.clear()


class MultipartReader(FormReader):
    """Process multipart formdata."""

    __slots__ = (
        "charset",
        "curname",
        "curvalue",
        "form",
        "headers",
        "max_size",
        "name",
        "partdata",
        "upload_to",
    )

    def __init__(self, charset: str, upload_to: "UploadHandler | None", max_size: int) -> None:
        super().__init__(charset)
        self.name = ""
        self.headers: dict[bytes, bytes] = {}
        self.partdata: Any = BytesIO()
        self.upload_to = upload_to
        self.max_size = max_size

    def init_parser(self, request: "Request", max_size: int) -> BaseParser:
        boundary = request.media.get("boundary", "")
        if not boundary:
            raise ValueError("Invalid content type boundary")

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

    def on_header_field(self, data: bytes, start: int, end: int) -> None:
        self.curname += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int) -> None:
        self.curvalue += data[start:end]

    def on_header_end(self, *_: Any) -> None:
        self.headers[bytes(self.curname.lower())] = bytes(self.curvalue)
        self.curname.clear()
        self.curvalue.clear()

    def on_headers_finished(self, *_args: Any) -> None:
        _, options = parse_options_header(
            (self.headers.get(b"content-disposition") or b"").decode(self.charset),
        )
        self.name = options.get("name", "")
        if not self.name:
            raise ValueError("Multipart part is missing a name")

        if "filename" in options:
            upload_to = self.upload_to
            partdata: Any
            if upload_to is not None:
                partdata = open(upload_to(options["filename"]), "wb+")  # noqa: SIM115, PTH123

            else:
                partdata = SpooledTemporaryFile(self.max_size)  # noqa: SIM115
                cast("Any", partdata._file).name = options["filename"]

            cast("Any", partdata).content_type = self.headers.get(b"content-type", b"").decode(
                self.charset
            )
            self.partdata = partdata

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        self.partdata.write(data[start:end])

    def on_part_end(self, *_: Any) -> None:
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
