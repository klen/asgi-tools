import inspect

import pytest


def pytest_collection_modifyitems(session, config, items):
    """Mark all async functions."""
    for item in items:
        if isinstance(item, pytest.Function) and inspect.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
