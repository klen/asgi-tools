async def test_compat():
    from asgi_tools._compat import aio_wait, aio_sleep, FIRST_COMPLETED

    async def coro(num):
        await aio_sleep(1e-2 * num)
        return num

    results = await aio_wait(coro(1), coro(2), coro(3))
    assert sorted(results) == [1, 2, 3]

    result = await aio_wait(coro(1), coro(2), coro(3), strategy=FIRST_COMPLETED)
    assert result == 1
