async def test_compat_aio():
    from asgi_tools._compat import aio_wait, aio_sleep, FIRST_COMPLETED

    async def coro(num):
        await aio_sleep(1e-2 * num)
        return num

    results = await aio_wait(coro(1), coro(2), coro(3))
    assert sorted(results) == [1, 2, 3]

    result = await aio_wait(coro(1), coro(2), coro(3), strategy=FIRST_COMPLETED)
    assert result == 1


def test_compat_json():
    from asgi_tools._compat import json_loads, json_dumps

    data = json_dumps({'test': 42})
    assert data
    assert isinstance(data, bytes)

    data = json_loads(data)
    assert data
    assert data == {'test': 42}
