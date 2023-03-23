"""test middlewares"""
from __future__ import annotations

import pytest


async def test_response_middleware(client_cls):
    from asgi_tools import ResponseError, ResponseMiddleware

    # Test default response
    md = ResponseMiddleware()
    client = client_cls(md)
    res = await client.get("/")
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    async def simple_app(*args):
        return False

    app = ResponseMiddleware(simple_app)
    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "false"

    async def simple_app2(*args):
        raise ResponseError.BAD_GATEWAY()

    app2 = ResponseMiddleware(simple_app2)
    client = client_cls(app2)
    res = await client.get("/")
    assert res.status_code == 502
    assert await res.text() == "Invalid responses from another server/proxy"

    async def simple_app3(*args):
        return

    app3 = ResponseMiddleware(simple_app3)
    client = client_cls(app3)
    res = await client.get("/")
    assert res.status_code == 200
    assert await res.text() == "null"


async def test_request_response_middlewares(client_cls):
    from asgi_tools import RequestMiddleware, ResponseMiddleware

    async def simple_app(request, receive, send):
        data = await request.json()
        first_name = data.get("first_name", "Anonymous")
        last_name = request.query.get("last_name", "Test")
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    app = RequestMiddleware(ResponseMiddleware(simple_app))

    client = client_cls(app)
    res = await client.post(
        "/testurl?last_name=Daniels",
        json={"first_name": "Jack"},
        headers={"test-header": "test-value"},
        cookies={"session": "test-session"},
    )
    assert res.status_code == 200
    assert await res.text() == "Hello Jack Daniels from '/testurl'"
    assert res.headers["content-length"] == str(
        len("Hello Jack Daniels from '/testurl'"),
    )


async def test_lifespan_middleware(client_cls):
    from asgi_tools import LifespanMiddleware

    side_effects = []

    async def simple_app(scope, receive, send):
        return None

    app = LifespanMiddleware(
        simple_app,
        on_startup=lambda: side_effects.append("started"),
        on_shutdown=lambda: side_effects.append("finished"),
    )
    client = client_cls(app)

    async with client.lifespan():
        assert ["started"] == side_effects

    assert ["started", "finished"] == side_effects


async def test_lifespan_middleware_errors(client_cls):
    from asgi_tools import LifespanMiddleware

    side_effects = {}

    async def fail():
        raise Exception

    async def start():
        side_effects["started"] = True

    async def simple_app(scope, receive, send):
        return None

    app = LifespanMiddleware(
        simple_app,
        on_startup=[fail, start],
        on_shutdown=lambda: side_effects.setdefault("finished", True),
    )
    client = client_cls(app)

    async with client.lifespan():
        assert "started" not in side_effects

    assert "finished" not in side_effects

    app = LifespanMiddleware.setup(ignore_errors=True)(
        lambda scope, receive, send: None,
        on_startup=[fail, start],
        on_shutdown=lambda: side_effects.setdefault("finished", True),
    )
    client = client_cls(app)

    async with client.lifespan():
        assert side_effects["started"]

    assert side_effects["finished"]


async def test_router_middleware(client_cls):
    from asgi_tools import Response, RouterMiddleware

    app = RouterMiddleware()

    with pytest.raises(app.router.RouterError):
        app.route("/test")("something")

    @app.route("/page1")
    async def page1(scope, receive, send):
        res = Response("page1")
        return await res(scope, receive, send)

    @app.route("/page2/{mode}", methods=["POST"])
    async def page2(scope, receive, send):
        mode = scope["path_params"]["mode"]
        res = Response(f"page2: {mode}")
        return await res(scope, receive, send)

    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    res = await client.get("/page1")
    assert res.status_code == 200
    assert await res.text() == "page1"

    res = await client.get("/page2/42")
    assert res.status_code == 404  # Returns default application

    res = await client.post("/page2/42")
    assert res.status_code == 200
    assert await res.text() == "page2: 42"


async def test_router_middleware2(client_cls):
    from asgi_tools import ResponseError, ResponseMiddleware, RouterMiddleware

    async def page404(scope, receive, send):
        return ResponseError.NOT_FOUND()

    router = RouterMiddleware(page404)
    app = ResponseMiddleware(router)

    @router.route("/page1")
    async def page1(scope, receive, send):
        return "page1"

    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 404
    assert await res.text() == "Nothing matches the given URI"

    res = await client.get("/page1")
    assert res.status_code == 200
    assert await res.text() == "page1"


async def test_staticfiles_middleware(client_cls, app):
    from pathlib import Path

    from asgi_tools import StaticFilesMiddleware

    app = StaticFilesMiddleware(app, folders=["/", Path(__file__).parent])

    client = client_cls(app)
    res = await client.get("/")
    assert res.status_code == 200
    body = await res.body()
    assert body == b"OK"

    res = await client.head("/static/test_middlewares.py")
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/x-python"
    assert not await res.text()

    res = await client.get("/static/test_middlewares.py")
    assert res.status_code == 200
    text = await res.text()
    assert text.startswith('"""test middlewares"""')

    res = await client.get("/static/unknown")
    assert res.status_code == 404

    res = await client.get("/static")
    assert res.status_code == 404


async def test_background_middleware(client_cls, app):
    from asgi_tools import BackgroundMiddleware, ResponseText, RouterMiddleware
    from asgi_tools._compat import aio_sleep

    router = RouterMiddleware()
    app = BackgroundMiddleware(router)
    results = []

    async def background_task(name):
        await aio_sleep(1e-1)
        results.append(name)

    @router.route("/test")
    async def test(scope, receive, send):
        BackgroundMiddleware.set_task(background_task("test1"))

        response = ResponseText("test")
        await response(scope, receive, send)

    client = client_cls(app)
    res = await client.get("/test")
    assert res.status_code == 200
    assert results == ["test1"]
