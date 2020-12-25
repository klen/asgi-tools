import inspect

import pytest
from httpx import AsyncClient


def pytest_collection_modifyitems(session, config, items):
    """Mark all async functions."""
    for item in items:
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


@pytest.fixture(scope='session')
def client():

    def fabric(app):
        return AsyncClient(app=app, base_url='http://testserver')

    return fabric
