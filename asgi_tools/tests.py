from http import cookies
from json import loads, dumps
from functools import partial
from urllib.parse import urlencode
from yarl import URL
from email.mime import multipart
from email.mime import nonmultipart

from .response import Response
from .utils import parse_headers, parse_cookies


class TestResponse(Response):

    def __init__(self):
        super(TestResponse, self).__init__(content=b'', status_code=None)

    async def feed(self, msg):
        if msg.get('type') == 'http.response.start':
            self.status_code = msg.get('status')
            self.headers = parse_headers(msg.get('headers', []))
            self.cookies = parse_cookies(self.headers.get('set-cookie'))

        if msg.get('type') == 'http.response.body':
            self.content += msg.get('body', b'')

    @property
    def body(self):
        return self.content

    @property
    def text(self):
        return self.content.decode(self.charset)

    def json(self):
        return loads(self.text)


class TestClient:

    def __init__(self, app, base_url='http://localhost'):
        self.app = app
        self.cookies = cookies.SimpleCookie()
        self.base_url = URL(base_url)

    # TODO: WebSockets, Request/Response Streams
    async def request(
            self, path, method='GET', query='', headers=None, data=b'',
            json=None, cookies=None, files=None, allow_redirects=True):

        headers = headers or {}
        res = TestResponse()

        if isinstance(data, str):
            data = data.encode(res.charset)

        if isinstance(data, dict):
            headers['Content-Type'], data = encode_multipart_formdata(data)
            data = data.encode(res.charset)

        if json is not None:
            headers['Content-Type'] = 'application/json'
            data = dumps(json).encode(res.charset)

        if files:
            headers['Content-Type'], data = encode_multipart_formdata(files)
            data = data.encode(res.charset)

        async def receive():
            return {'type': 'http.request', 'body': data, 'mode_body': False}

        headers.setdefault('Content-Length', str(len(data)))
        await self.app(self.build_scope(
            path, headers=headers, query=query, cookies=cookies, type='http', method=method,
        ), receive, res.feed)

        if allow_redirects and res.status_code in {301, 302, 303, 307, 308}:
            return await self.get(res.headers['location'])

        return res

    async def websocket(self, path, query=None, headers=None, data=b'', cookies=None):
        headers = headers or {}

        async def send(msg):
            breakpoint()

        async def receive():
            breakpoint()

        await self.app(self.build_scope(
            path, headers=headers, query=query, cookies=cookies, type='websocket'
        ), receive, send)

    def __getattr__(self, name):
        return partial(self.request, method=name.upper())

    def build_scope(
            self, path, headers=None, query=None, cookies=None, **scope):
        """Prepare a request scope."""
        headers = headers or {}
        headers.setdefault('Remote-Addr', '127.0.0.1')
        headers.setdefault('User-Agent', 'ASGI-Tools-Test-Client')
        headers.setdefault('Host', self.base_url.host)

        if cookies:
            for c, v in cookies.items():
                self.cookies[c] = v

        if len(self.cookies):
            headers.setdefault('Cookie', self.cookies.output(header=''))

        path = URL(path)
        query = query or path.query_string

        if isinstance(query, dict):
            query = urlencode(query, doseq=True)

        return dict({
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'path': path.path,
            'query_string': query.encode(),
            'root_path': '',
            'scheme': scope.get('type') == 'http' and self.base_url.scheme or 'ws',
            'headers': [
                (key.lower().encode('latin-1'), str(val).encode('latin-1'))
                for key, val in (headers or {}).items()
            ],
            'server': ('127.0.0.1', self.base_url.port),
        }, **scope)


class MIMEFormdata(nonmultipart.MIMENonMultipart):

    def __init__(self, keyname, *args, **kwargs):
        super(MIMEFormdata, self).__init__(*args, **kwargs)
        self.add_header(
            "Content-Disposition", "form-data; name=\"%s\"" % keyname)


def encode_multipart_formdata(fields):
    # Based on https://julien.danjou.info/handling-multipart-form-data-python/
    m = multipart.MIMEMultipart("form-data")

    for field, value in fields.items():
        data = MIMEFormdata(field, "text", "plain")
        if hasattr(value, 'read'):
            value = value.read()

        data.set_payload(str(value))
        m.attach(data)

    header, _, data = str(m).partition('\n')
    return header[len('Content-Type: '):], data

# pylama:ignore=D
