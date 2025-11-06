from __future__ import annotations

import pytest
import uvloop


@pytest.fixture(
    params=[
        pytest.param(("asyncio", {"loop_factory": None}), id="asyncio"),
        pytest.param(("asyncio", {"loop_factory": uvloop.new_event_loop}), id="asyncio+uvloop"),
        "trio",
        "curio",
    ],
)
def aiolib(request):
    return request.param


@pytest.fixture(scope="session")
def client_cls():
    from asgi_tools.tests import ASGITestClient

    return ASGITestClient


@pytest.fixture()
def app():
    from asgi_tools import App

    app = App(debug=True)

    @app.route("/")
    async def index(request):
        return "OK"

    return app


@pytest.fixture()
def client(app, client_cls):
    return client_cls(app)


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


@pytest.fixture()
def gen_request(client, send):
    from asgi_tools import Request

    def gen_request(path="/", body=None, scope_type="http", method="GET", **opts):
        scope = client.build_scope(path, type=scope_type, method=method, **opts)

        body = list(body) if body else []

        async def receive():
            chunk = body.pop(0)
            return {"body": chunk, "more_body": bool(len(body))}

        return Request(scope, receive, send)

    return gen_request
