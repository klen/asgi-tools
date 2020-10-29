from cgi import parse_header, parse_multipart
from functools import wraps, cached_property
from http import cookies
from io import BytesIO
from json import loads
from urllib.parse import parse_qsl

from multidict import CIMultiDict, MultiDict
from yarl import URL

from . import ASGIDecodeError, SUPPORTED_SCOPES, DEFAULT_CHARSET


def process_decode(meta=None, message=None):

    def decorator(amethod):

        @wraps(amethod)
        async def wrapper(self, *args, **kwargs):
            try:
                if not meta:
                    return await amethod(self, *args, **kwargs)
                if meta not in self._meta:
                    self._meta[meta] = await amethod(self, *args, **kwargs)
                return self._meta[meta]
            except (LookupError, ValueError):
                raise ASGIDecodeError(message)

        return wrapper
    return decorator


class Request:

    def __init__(self, scope, receive=None, send=None):
        assert scope["type"] in SUPPORTED_SCOPES
        self.scope = scope
        self.receive = receive
        content_type, opts = parse_header(self.headers.get('content-type', ''))
        self._meta = {
            'opts': opts,
            'content-type': content_type}
        self._body = None

    def __getattr__(self, name):
        return self.scope[name]

    def __iter__(self):
        return iter(self.scope)

    def __len__(self):
        return len(self.scope)

    def __str__(self):
        return f"{self.url.path}"

    def __repr__(self):
        return f"<Request '{ self }'"

    @cached_property
    def url(self):
        host, port = self.scope.get('server') or (None, None)
        host = self.headers.get('host') or host
        return URL.build(
            scheme=self.scope.get('scheme', 'http'),
            host=self.headers.get('host') or host,
            port=port, path=self.scope.get("root_path", "") + self.scope["path"],
            query_string=self.scope.get("query_string", b"").decode("latin-1")
        )

    @cached_property
    def headers(self):
        return CIMultiDict(
            [[v.decode('latin-1') for v in item] for item in self.scope.get('headers', [])])

    @cached_property
    def cookies(self):
        data = {}
        for chunk in self.headers.get('cookie', '').split(';'):
            key, _, val = chunk.partition('=')
            data[key.strip()] = cookies._unquote(val.strip())

        return data

    @property
    def query(self):
        return self.url.query

    @property
    def charset(self):
        return self._meta['opts'].get('charset', DEFAULT_CHARSET)

    @property
    def content_type(self):
        return self._meta['content-type']

    async def stream(self):
        if not self.receive:
            raise RuntimeError('Request doesnt have a receive coroutine')

        message = await self.receive()
        yield message.get('body', b'')
        while message.get('more_body'):
            message = await self.receive()
            yield message.get('body', b'')

    async def body(self):
        if self._body is None:
            chunks = []
            async for chunk in self.stream():
                chunks.append(chunk)

            self._body = b"".join(chunks)

        return self._body

    @process_decode(message='Invalid Encoding')
    async def text(self):
        body = await self.body()
        charset = self.charset or DEFAULT_CHARSET
        return body.decode(charset)

    @process_decode(meta='json', message='Invalid JSON')
    async def json(self):
        text = await self.text()
        return loads(text)

    @process_decode(meta='form', message='Invalid Form Data')
    async def form(self):
        form = MultiDict()

        # TODO: Improve multipart parsing
        if self.content_type == 'multipart/form-data':
            pdict = dict(self._meta['opts'])
            pdict['boundary'] = bytes(pdict.get('boundary', ''), self.charset)
            pdict['CONTENT-LENGTH'] = self.headers.get('content-length')
            data = parse_multipart(BytesIO(await self.body()), pdict, encoding=self.charset)
            for name, values in data.items():
                for val in values:
                    form[name] = val

            return form

        data = await self.body()
        query = data.decode(self.charset)
        form.extend(parse_qsl(qs=query, keep_blank_values=True, encoding=self.charset))

        return form
