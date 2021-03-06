import pytest


@pytest.fixture(params=[
    pytest.param(('asyncio', {'use_uvloop': False}), id='asyncio'),
    pytest.param(('asyncio', {'use_uvloop': True}), id='asyncio+uvloop'),
    'trio', 'curio'
])
def aiolib(request):
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
