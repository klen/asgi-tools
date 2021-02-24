import pytest


@pytest.fixture(params=[
    pytest.param('asyncio'),
    pytest.param('trio'),
    pytest.param('curio'),
], autouse=True)
def anyio_backend(request):
    return request.param


@pytest.fixture(scope='session')
def Client():
    from asgi_tools.tests import ASGITestClient

    return ASGITestClient


@pytest.fixture
def app():

    from asgi_tools import App

    app = App(debug=True)

    @app.route('/')
    async def index(request):
        return 'OK'

    return app


@pytest.fixture
def client(app, Client):
    return Client(app)
