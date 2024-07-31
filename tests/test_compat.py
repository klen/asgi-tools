from __future__ import annotations

import asyncio
from multiprocessing import Value

import pytest

from asgi_tools._compat import FIRST_COMPLETED, aio_sleep, aio_timeout, aio_wait


async def test_aio_sleep():
    await aio_sleep(1e-2)


async def test_aio_timeout_disabled():
    async with aio_timeout(0):
        await aio_sleep(1e-2)


async def test_aio_timeout():
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):  # python 39, 310
        async with aio_timeout(1e-2):
            await aio_sleep(1)


async def coro(num, exc=None):
    await aio_sleep(1e-2 * num)
    if exc:
        raise exc
    return num


async def test_aio_wait():
    results = await aio_wait(coro(3), coro(2), coro(1))
    assert sorted(results) == [1, 2, 3]


async def test_aio_wait_first_completed():
    result = await aio_wait(coro(3), coro(2), coro(1), strategy=FIRST_COMPLETED)
    assert result == 1


def test_compat_json():
    from asgi_tools._compat import json_dumps, json_loads

    data = json_dumps({"test": 42})
    assert data
    assert isinstance(data, bytes)

    data = json_loads(data)
    assert data
    assert data == {"test": 42}
