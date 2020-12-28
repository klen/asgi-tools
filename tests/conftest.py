import pytest
from httpx import AsyncClient


@pytest.fixture(params=[
    pytest.param('asyncio'),
    pytest.param('trio'),
], autouse=True)
def anyio_backend(request):
    return request.param


@pytest.fixture(scope='session')
def client():

    def fabric(app):
        return AsyncClient(app=app, base_url='http://testserver')

    return fabric


@pytest.fixture
def app():

    from asgi_tools import App

    app = App()

    @app.route('/')
    async def index(request):
        return 'OK'

    return app
