# cython: language_level=3

"""Work with multipart."""

from io import BytesIO
from cgi import parse_header
from pathlib import Path
from tempfile import SpooledTemporaryFile
from urllib.parse import unquote_to_bytes

from multidict import MultiDict

from .multipart cimport QueryStringParser, MultipartParser, BaseParser


async def read_formdata(object request, int max_size, object upload_to,
                        int file_memory_limit=1024 * 1024) -> MultiDict:
    """Read formdata from the given request."""
    cdef str content_type = request.content_type
    if content_type == 'multipart/form-data':
        reader = MultipartReader(request.charset, upload_to, file_memory_limit)
    else:
        reader = FormReader(request.charset)

    parser = reader.init_parser(request, max_size)
    async for chunk in request.stream():
        parser.write(chunk)

    parser.finalize()
    return reader.form


cdef class FormReader:
    """Parse querystring form data."""

    cdef str charset
    cdef bytearray curname
    cdef bytearray curvalue
    cdef public object form

    def __init__(self, str charset):
        self.charset = charset
        self.curname = bytearray()
        self.curvalue = bytearray()
        self.form: MultiDict = MultiDict()

    cpdef BaseParser init_parser(self, object request, int max_size):
        return QueryStringParser({
            'field_name': self.on_field_name,
            'field_data': self.on_field_data,
            'field_end': self.on_field_end
        }, max_size=max_size)

    def on_field_name(self, bytes data, int start, int end):
        self.curname += data[start:end]

    def on_field_data(self, bytes data, int start, int end):
        self.curvalue += data[start:end]

    def on_field_end(self, bytes data, int start, int end):
        self.form.add(
            unquote_plus(bytes(self.curname)).decode(self.charset),
            unquote_plus(bytes(self.curvalue)).decode(self.charset),
        )
        self.curname.clear()
        self.curvalue.clear()


cdef class MultipartReader(FormReader):
    """Parse multipart formdata."""

    cdef str name
    cdef dict headers
    cdef object partdata
    cdef object upload_to
    cdef int file_memory_limit

    def __init__(self, str charset, object upload_to, int file_memory_limit):
        self.curname = bytearray()
        self.curvalue = bytearray()
        self.form: MultiDict = MultiDict()
        self.charset = charset
        self.name = ''
        self.headers = {}
        self.partdata = BytesIO()
        self.upload_to = upload_to
        self.file_memory_limit = file_memory_limit

    cpdef BaseParser init_parser(self, object request, int max_size):
        cdef str boundary = request.media.get('boundary', '')
        if not len(boundary):
            raise ValueError('Invalid content type boundary')

        return MultipartParser(request.media.get('boundary'), {
            'header_end': self.on_header_end,
            'header_field': self.on_header_field,
            'headers_finished': self.on_headers_finished,
            'header_value': self.on_header_value,
            'part_data': self.on_part_data,
            'part_end': self.on_part_end,
        }, max_size=max_size)

    def on_header_field(self, data: bytes, start: int, end: int):
        self.curname += data[start:end]

    def on_header_value(self, data: bytes, start: int, end: int):
        self.curvalue += data[start:end]

    def on_header_end(self, data: bytes, start: int, end: int):
        self.headers[bytes(self.curname.lower())] = bytes(self.curvalue)
        self.curname.clear()
        self.curvalue.clear()

    def on_headers_finished(self, data: bytes, start: int, end: int):
        _, options = parse_header(self.headers[b'content-disposition'].decode(self.charset))
        self.name = options['name']
        upload_to = self.upload_to
        if 'filename' in options:
            if upload_to is not None:
                filename = upload_to(options['filename'])
                self.partdata = f = open(filename, 'wb+')

            else:
                self.partdata = f = SpooledTemporaryFile(self.file_memory_limit)
                f._file.name = options['filename']

            f.content_type = self.headers[b'content-type'].decode(self.charset)

    def on_part_data(self, data: bytes, start: int, end: int):
        self.partdata.write(data[start:end])

    def on_part_end(self, data: bytes, start: int, end: int):
        field_data = self.partdata
        if isinstance(field_data, BytesIO):
            self.form.add(self.name, field_data.getvalue().decode(self.charset))

        else:
            field_data.seek(0)
            self.form.add(self.name, field_data)

        self.partdata = BytesIO()
        self.headers = {}


cdef dict _hextobyte = {
    (a + b).encode(): bytes.fromhex(a + b)
    for a in '0123456789ABCDEFabcdef' for b in '0123456789ABCDEFabcdef'
}


cdef bytes unquote_plus(value: bytes):
    value = value.replace(b'+', b' ')
    bits = value.split(b'%')
    if len(bits) == 1:
        return value
    res = bits[0]
    for item in bits[1:]:
        try:
            res += _hextobyte[item[:2]]
            res += item[2:]
        except KeyError:
            res += b'%'
            res += item

    return res

# pylama: ignore=D
