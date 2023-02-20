import pytest


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"use_uvloop": False}), id="asyncio"),
        pytest.param(("asyncio", {"use_uvloop": True}), id="asyncio+uvloop"),
        "trio",
        "curio",
    ]
)
def aiolib(request):
    return request.param


@pytest.fixture(scope="session")
def Client():
    from asgi_tools.tests import ASGITestClient

    return ASGITestClient


@pytest.fixture
def app():
    from asgi_tools import App

    app = App(debug=True)

    @app.route("/")
    async def index(request):
        return "OK"

    return app


@pytest.fixture
def client(app, Client):
    return Client(app)


@pytest.fixture(scope="session")
def receive():
    async def receive():
        return {"type": "http.request"}

    return receive


@pytest.fixture(scope="session")
def send():
    async def send(message):
        pass

    return send


@pytest.fixture
def GenRequest(client, send):
    from asgi_tools import Request

    def gen_request(path="/", body=None, type="http", method="GET", **opts):
        scope = client.build_scope(path, type=type, method=method, **opts)

        body = list(body) if body else []

        async def receive():
            chunk = body.pop(0)
            return {"body": chunk, "more_body": bool(len(body))}

        request = Request(scope, receive, send)
        return request

    return gen_request
