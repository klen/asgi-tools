"""Application Tests."""
from __future__ import annotations

from pathlib import Path
from unittest import mock


async def test_app(client_cls):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])

    @app.route("/test/{param}", methods="get")
    async def test_request(request):
        return "Done %s" % request.path_params["param"]

    client = client_cls(app)

    res = await client.get("/404")
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    res = await client.get("/static/test_app.py")
    assert res.status_code == 200
    text = await res.text()
    assert text.startswith('"""Application Tests."""')

    res = await client.post("/test/42")
    assert res.status_code == 405
    assert await res.text() == "Specified method is invalid for this resource"

    @app.route("/data", methods="post")
    async def test_data(request):
        data = await request.data()
        return dict(data)

    res = await client.post("/data", json={"test": "passed"})
    assert res.status_code == 200
    assert await res.json() == {"test": "passed"}

    @app.route("/none")
    async def test_none(request):
        return

    res = await client.get("/none")
    assert res.status_code == 200

    @app.route("/path_params")
    async def path_params(request):
        return request["path_params"].get("unknown", 42)

    res = await client.get("/path_params")
    assert res.status_code == 200
    assert await res.text() == "42"

    @app.route("/sync")
    def sync_fn(request):
        return "Sync is ok"

    res = await client.get("/sync")
    assert res.status_code == 200
    assert await res.text() == "Sync is ok"


async def test_scope_endpoint(client_cls):
    from asgi_tools.app import App, ResponseError

    app = App()
    client = client_cls(app)

    @app.route("/")
    async def endpoint(request):
        return request.scope["endpoint"].__qualname__

    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "test_scope_endpoint.<locals>.endpoint"


async def test_errors(client_cls):
    from asgi_tools.app import App, ResponseError

    app = App()
    client = client_cls(app)

    @app.route("/502")
    async def test_response_error(request):
        raise ResponseError.BAD_GATEWAY()

    res = await client.get("/502")
    assert res.status_code == 502
    assert await res.text() == "Invalid responses from another server/proxy"

    @app.route("/error")
    async def test_unhandled_exception(request):
        raise RuntimeError("An exception")

    res = await client.get("/error")
    assert res.status_code == 500
    assert await res.text() == "Server got itself in trouble"


async def test_trim_last_slach(client_cls):
    from asgi_tools.app import App

    app = App()
    client = client_cls(app)

    @app.route("/route1")
    async def route1(request):
        return "route1"

    @app.route("/route2/")
    async def route2(request):
        return "route2"

    res = await client.get("/route1")
    assert res.status_code == 200

    res = await client.get("/route2/")
    assert res.status_code == 200

    res = await client.get("/route1/")
    assert res.status_code == 404

    res = await client.get("/route2")
    assert res.status_code == 404

    app = App(trim_last_slash=True)
    client = client_cls(app)

    @app.route("/route1")
    async def route11(request):
        return "route1"

    @app.route("/route2/")
    async def route21(request):
        return "route2"

    res = await client.get("/route1")
    assert res.status_code == 200

    res = await client.get("/route2/")
    assert res.status_code == 200

    res = await client.get("/route1/")
    assert res.status_code == 200

    res = await client.get("/route2")
    assert res.status_code == 200


async def test_app_static(client_cls):
    from asgi_tools.app import App

    app = App(static_folders=[Path(__file__).parent])
    client = client_cls(app)

    async with client.lifespan():
        res = await client.get("/static/test_app.py")
        assert res.status_code == 200
        text = await res.text()
        assert text.startswith('"""Application Tests."""')


async def test_app_handle_exception(client_cls):
    from asgi_tools.app import App, ResponseError

    app = App()

    @app.route("/500")
    async def raise_unknown(request):
        raise Exception("Unknown Exception")

    @app.route("/501")
    async def raise_response_error(request):
        res = ResponseError(status_code=501)
        raise res

    # By default we handle all exceptions as INTERNAL SERVER ERROR 500 Response
    client = client_cls(app)
    res = await client.get("/500")
    assert res.status_code == 500
    assert await res.text() == "Server got itself in trouble"

    @app.on_error(Exception)
    async def handle_unknown(request, exc):
        return "UNKNOWN: %s" % exc

    @app.on_error(ResponseError)
    async def handler(request, response):
        if response.status_code == 404:
            return "Response 404"
        return "Custom Server Error"

    async with client.lifespan():
        res = await client.get("/500")
        assert res.status_code == 200
        assert await res.text() == "UNKNOWN: Unknown Exception"

        res = await client.get("/404")
        assert res.status_code == 200
        assert await res.text() == "Response 404"

        res = await client.get("/501")
        assert res.status_code == 200
        assert await res.text() == "Custom Server Error"


async def test_app_middleware_simple(client, app):
    from asgi_tools import ResponseHTML

    md_mock = mock.MagicMock()

    @app.route("/err")
    async def err(request):
        raise RuntimeError("Handle me")

    @app.on_error(Exception)
    async def custom_exc(request, exc):
        return ResponseHTML("App Exception")

    res = await client.get("/err")
    assert res.status_code == 200
    assert await res.text() == "App Exception"

    @app.middleware
    async def first_md(app, request, receive, send):
        md_mock("first start")
        try:
            response = await app(request, receive, send)
            if "x-second-md" in response.headers:
                response.headers["x-first-md"] = response.headers["x-second-md"]
            return response
        except RuntimeError:
            return ResponseHTML("Middleware Exception")
        finally:
            md_mock("first exit")

    @app.middleware
    async def second_md(app, request, receive, send):
        md_mock("second start")
        try:
            response = await app(request, receive, send)
            response.headers["x-second-md"] = "passed"
            return response
        finally:
            md_mock("second exit")

    res = await client.get("/")
    assert res.status_code == 200
    assert res.headers["x-first-md"] == "passed"
    assert res.headers["x-second-md"] == "passed"
    assert [args[0][0] for args in md_mock.call_args_list] == [
        "first start",
        "second start",
        "second exit",
        "first exit",
    ]

    res = await client.get("/404")
    assert res.status_code == 404
    assert "x-first-md" not in res.headers
    assert "x-second-md" not in res.headers

    res = await client.get("/err")
    assert res.status_code == 200
    assert await res.text() == "Middleware Exception"


#  @pytest.mark.skip
async def test_app_middleware_classic(client, app):
    from asgi_tools import ResponseError, ResponseHTML

    @app.route("/err")
    async def err(request):
        raise RuntimeError("Handle me")

    @app.on_error(Exception)
    async def custom_exc(request, exc):
        return ResponseHTML("App Exception")

    @app.middleware
    def classic_md(app):
        async def middleware(scope, receive, send):
            headers = scope["headers"]
            auth = [v for k, v in headers if k == b"authorization"]
            if not auth:
                response = ResponseError.UNAUTHORIZED()
                await response(scope, receive, send)
                return

            await app(scope, receive, send)

        return middleware

    res = await client.get("/")
    assert res.status_code == 401

    res = await client.get("/", headers={"authorization": "any"})
    assert res.status_code == 200
    assert await res.text() == "OK"

    res = await client.get("/err", headers={"authorization": "any"})
    assert res.status_code == 200
    assert await res.text() == "App Exception"


async def test_cbv(app, client):
    from asgi_tools import HTTPView

    @app.route("/cbv")
    class Custom(HTTPView):
        async def get(self, request):
            return "CBV: get"

        async def post(self, request):
            return "CBV: post"

    res = await client.get("/cbv")
    assert res.status_code == 200
    assert await res.text() == "CBV: get"

    res = await client.post("/cbv")
    assert res.status_code == 200
    assert await res.text() == "CBV: post"

    res = await client.put("/cbv")
    assert res.status_code == 405


async def test_websockets(app, client):
    from asgi_tools import ResponseWebSocket

    @app.route("/websocket")
    async def websocket(request):
        ws = ResponseWebSocket(request)
        await ws.accept()
        msg = await ws.receive()
        assert msg == "ping"
        await ws.send("pong")
        await ws.close()

    async with client.websocket("/websocket") as ws:
        await ws.send("ping")
        msg = await ws.receive()
        assert msg == "pong"

    res = await client.get("/")
    assert res.status_code == 200


async def test_app_lifespan(app, client):
    side_effects = {}

    @app.on_startup
    def start():
        side_effects["started"] = True

    @app.on_shutdown
    def finish():
        side_effects["finished"] = True

    async with client.lifespan():
        assert side_effects["started"]
        res = await client.get("/")
        assert res.status_code == 200

    assert side_effects["finished"]


async def test_nested(app, client):
    from asgi_tools.app import App

    @app.middleware
    async def mid(app, request, receive, send):
        response = await app(request, receive, send)
        response.headers["x-app"] = "OK"
        return response

    subapp = App()

    @subapp.middleware
    async def submid(app, request, receive, send):
        response = await app(request, receive, send)
        response.headers["x-subapp"] = "OK"
        return response

    @subapp.route("/route")
    async def route(request):
        return "OK from subapp"

    app.route("/sub")(subapp)

    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "OK"
    assert res.headers["x-app"] == "OK"

    res = await client.get("/sub/route")
    assert res.status_code == 200
    assert await res.text() == "OK from subapp"
    assert res.headers["x-subapp"] == "OK"
    assert res.headers["x-app"] == "OK"
