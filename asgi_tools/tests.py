import typing as t
from collections import deque
from email.mime import multipart, nonmultipart
from functools import partial
from http import cookies
from json import loads, dumps
from urllib.parse import urlencode

from yarl import URL

from . import ASGIConnectionClosed
from ._compat import aio_sleep, aio_spawn, asynccontextmanager, wait_for_first
from ._types import JSONType, Scope, Receive, Send, Message
from .middleware import ASGIApp
from .response import Response, ResponseWebSocket, parse_websocket_msg
from .utils import to_awaitable, parse_headers


class TestResponse(Response):

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        self._receive = receive
        msg = await self._receive()
        assert msg.get('type') == 'http.response.start', 'Invalid Response'
        self.status_code = int(msg.get('status', 502))
        self.headers = parse_headers(msg.get('headers', []))
        for cookie in self.headers.getall('set-cookie', []):
            self.cookies.load(cookie)

    async def stream(self) -> t.AsyncGenerator[bytes, None]:
        """Stream the response."""
        more_body = True
        while more_body:
            msg = await self._receive()
            if msg.get('type') == 'http.response.body':
                chunk = msg.get('body')
                if chunk:
                    yield chunk
                more_body = msg.get('more_body', False)

    async def body(self) -> bytes:
        """Load response body."""
        _body = b''
        async for chunk in self.stream():
            _body += chunk
        return _body

    async def text(self) -> str:
        body = await self.body()
        return body.decode(self.charset)

    async def json(self) -> JSONType:
        text = await self.text()
        return loads(text)


class TestWebSocketResponse(ResponseWebSocket):

    # Disable app methods for clients
    accept = close = None  # type: ignore

    def connect(self) -> t.Coroutine[Message, t.Any, t.Any]:
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
        if not msg['type'].startswith('websocket.'):
            raise ValueError('Invalid websocket message: %r', msg)

        if msg['type'] == 'websocket.accept':
            self.partner_state = self.STATES.connected
            return await self.receive(raw=raw)

        if msg['type'] == 'websocket.close':
            self.partner_state == self.STATES.disconnected
            raise ASGIConnectionClosed('Connection has been closed.')

        return raw and msg or parse_websocket_msg(msg, charset=self.charset)


class ASGITestClient:
    """The test client allows you to make requests against an ASGI application.

    Features:

    * cookies
    * multipart/form-data
    * follow redirects
    * response streams
    * request streams
    * websocket support

    """

    def __init__(self, app: ASGIApp, base_url: str = 'http://localhost'):
        self.app = app
        self.base_url = URL(base_url)
        self.cookies: cookies.SimpleCookie = cookies.SimpleCookie()
        self.headers: t.Dict[str, str] = {}

    def __getattr__(self, name: str) -> t.Callable[..., t.Awaitable]:
        return partial(self.request, method=name.upper())

    async def request(
            self, path: str, method: str = 'GET', query: t.Union[str, t.Dict] = '',
            headers: t.Dict[str, str] = None, data: t.Union[bytes, str, t.Dict] = b'',
            json: JSONType = None, cookies: t.Dict = None, files: t.Dict = None,
            follow_redirect: bool = True, timeout: float = 0.3) -> TestResponse:
        """Make a HTTP request.

        .. code-block:: python

            from asgi_tools import App, ASGITestClient

            app = Application()

            @app.route('/')
            async def index(request):
                return 'OK'

            async def test_app():
                client = ASGITestClient(app)
                response = await client.get('/')
                assert response.status_code == 200
                assert await response.text() == 'OK'
        """

        res = TestResponse()
        headers = headers or dict(self.headers)

        if isinstance(data, str):
            data = data.encode(res.charset)

        elif isinstance(data, dict):
            headers['Content-Type'], data = encode_multipart_formdata(data)
            data = data.encode(res.charset)

        elif json is not None:
            headers['Content-Type'] = 'application/json'
            data = dumps(json).encode(res.charset)

        elif files:
            headers['Content-Type'], data = encode_multipart_formdata(files)
            data = data.encode(res.charset)

        headers.setdefault('Content-Length', str(len(data)))

        receive_from_client, send_to_app = simple_stream()
        receive_from_app, send_to_client = simple_stream()

        # Prepare a request data
        await send_to_app({'type': 'http.request', 'body': data, 'more_body': False})

        scope = self.build_scope(
            path, headers=headers, query=query, cookies=cookies, type='http', method=method,
        )

        await wait_for_first(
            self.app(scope, receive_from_client, send_to_client),
            raise_timeout(timeout),
        )
        await send_to_client({'type': 'http.response.body', 'more_body': False})
        await res(scope, receive_from_app, send_to_app)
        for n, v in res.cookies.items():
            self.cookies[n] = v

        if follow_redirect and res.status_code in {301, 302, 303, 307, 308}:
            return await self.get(res.headers['location'])

        return res

    # TODO: Timeouts for websockets
    @asynccontextmanager
    async def websocket(self, path: str, query: t.Union[str, t.Dict] = None,
                        headers: t.Dict = None, cookies: t.Dict = None):
        """Connect to a websocket.

        .. code-block:: python

            from asgi_tools import App, ASGITestClient, ResponseWebSocket

            app = Application()

            @app.route('/websocket')
            async def websocket(request):
                async with ResponseWebSocket(request) as ws:
                    msg = await ws.receive()
                    assert msg == 'ping'
                    await ws.send('pong')

            async def test_app():
                client = ASGITestClient(app)
                await ws.send('ping')
                msg = await ws.receive()
                assert msg == 'pong'

        """
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
            self, path: str, headers: t.Dict = None, query: t.Union[str, t.Dict] = None,
            cookies: t.Dict = None, **scope) -> Scope:
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

        url = URL(path)
        query = query or url.query_string

        if isinstance(query, dict):
            query = urlencode(query, doseq=True)

        return dict({
            'asgi': {'version': '3.0'},
            'http_version': '1.1',
            'path': url.path,
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


def encode_multipart_formdata(fields: t.Dict) -> t.Tuple[str, str]:
    # Based on https://julien.danjou.info/handling-multipart-form-data-python/
    m = multipart.MIMEMultipart("form-data")

    for field, value in fields.items():
        data = MIMEFormdata(field, "text", "plain")
        if hasattr(value, 'read'):
            value = value.read()

        data.set_payload(str(value))
        m.attach(data)

    header, _, body = str(m).partition('\n')
    return header[len('Content-Type: '):], body


def simple_stream(maxlen=None):
    queue = deque(maxlen=maxlen)

    async def receive():
        while not queue:
            await aio_sleep(1e-3)
        return queue.popleft()

    return receive, to_awaitable(queue.append)


async def raise_timeout(timeout):
    await aio_sleep(timeout)
    raise TimeoutError('Timeout occured')

# pylama:ignore=D
