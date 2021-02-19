async def test_aio_sleep():
    from asgi_tools._compat import aio_sleep

    await aio_sleep(1e-2)


async def test_aio_spawn():
    from asgi_tools._compat import aio_spawn, aio_sleep

    SIDE_EFFECTS = {}

    async def task(name):
        SIDE_EFFECTS[name] = True

    async with aio_spawn(task, 'tests'):
        await aio_sleep(1e-2)

    assert SIDE_EFFECTS['tests'] is True


async def test_aio_wait():

    from asgi_tools._compat import aio_wait, aio_sleep, FIRST_COMPLETED

    async def task(name, time):
        await aio_sleep(time)
        return name

    assert 't2' == await aio_wait(task('t1', 2e-2), task('t2', 1e-2), strategy=FIRST_COMPLETED)
