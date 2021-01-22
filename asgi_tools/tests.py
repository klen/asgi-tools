import asyncio
from http import cookies
from json import loads, dumps
from functools import partial
from urllib.parse import urlencode
from yarl import URL
from email.mime import multipart
from email.mime import nonmultipart
from contextlib import asynccontextmanager
from collections import deque
from sniffio import current_async_library

from . import ASGIConnectionClosed
from .response import Response, ResponseWebSocket, parse_websocket_msg
from .utils import parse_headers, trio, to_awaitable


class TestResponse(Response):

    def __init__(self):
        super(TestResponse, self).__init__(content=b'', status_code=None)

    async def _receive_from_app(self, msg):
        if msg.get('type') == 'http.response.start':
            self.status_code = msg.get('status')
            self.headers = parse_headers(msg.get('headers', []))
            sc = cookies.SimpleCookie()
            for cookie in self.headers.getall('set-cookie', []):
                sc.load(cookie)
            self.cookies = {n: c.value for n, c in sc.items()}

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


class TestWebSocketResponse(ResponseWebSocket):

    # Disable app methods for clients
    accept = close = None  # type: ignore

    def connect(self):
        return self.send({'type': 'websocket.connect'})

    async def disconnect(self):
        await self.send({'type': 'websocket.disconnect'})
        self.state = self.STATES.disconnected

    def send(self, msg, type='websocket.receive'):
        """Send a message to a client."""
        return super().send(msg, type=type)

    async def receive(self, raw=False):
        """Receive messages from a client."""
        if self.partner_state == self.STATES.disconnected:
            raise ASGIConnectionClosed

        msg = await self._receive()
        if msg['type'] == 'websocket.accept':
            self.partner_state = self.STATES.connected
            return await self.receive(raw=raw)

        if msg['type'] == 'websocket.close':
            self.partner_state == self.STATES.disconnected
            raise ASGIConnectionClosed('Connection has been closed.')

        return raw and msg or parse_websocket_msg(msg, charset=self.charset)


class ASGITestClient:

    def __init__(self, app, base_url='http://localhost'):
        self.app = app
        self.base_url = URL(base_url)
        self.cookies = cookies.SimpleCookie()

    def __getattr__(self, name):
        return partial(self.request, method=name.upper())

    # TODO: Request/Response Streams
    async def request(
            self, path, method='GET', query='', headers=None, data=b'',
            json=None, cookies=None, files=None, allow_redirects=True):
        """Make a http request."""

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

        async def send():
            return {'type': 'http.request', 'body': data, 'mode_body': False}

        headers.setdefault('Content-Length', str(len(data)))
        await self.app(self.build_scope(
            path, headers=headers, query=query, cookies=cookies, type='http', method=method,
        ), send, res._receive_from_app)

        assert res.status_code, 'Response is not completed'
        for n, v in res.cookies.items():
            self.cookies[n] = v

        if allow_redirects and res.status_code in {301, 302, 303, 307, 308}:
            return await self.get(res.headers['location'])

        return res

    @asynccontextmanager
    async def websocket(self, path, query=None, headers=None, data=b'', cookies=None):
        """Connect to a websocket."""
        receive_from_client, send_to_app = simple_stream()
        receive_from_app, send_to_client = simple_stream()

        scope = self.build_scope(
            path, headers=headers, query=query, cookies=cookies, type='websocket'
        )
        ws = TestWebSocketResponse(scope, receive_from_client, send_to_client)
        async with aio_spawn(self.app, scope, receive_from_app, send_to_app):
            await ws.connect()
            yield ws
            await ws.disconnect()

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
            headers.setdefault('Cookie', self.cookies.output(header='', sep=';'))

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


def simple_stream(maxlen=None):
    queue = deque(maxlen=maxlen)

    async def receive():
        while not queue:
            await aio_sleep(1e-2)
        return queue.popleft()

    return receive, to_awaitable(queue.append)


# Compatibility (asyncio, trio)
# -----------------------------


def aio_sleep(seconds):
    """Return sleep coroutine."""
    if trio and current_async_library() == 'trio':
        return trio.sleep(seconds)
    return asyncio.sleep(seconds)


@asynccontextmanager
async def aio_spawn(fn, *args, **kwargs):
    if trio and current_async_library() == 'trio':
        async with trio.open_nursery() as tasks:
            yield tasks.start_soon(fn, *args, **kwargs)

    else:
        yield asyncio.create_task(fn(*args, **kwargs))

# pylama:ignore=D
