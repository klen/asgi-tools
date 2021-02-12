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

    assert SIDE_EFFECTS['tests'] == True


async def test_wait_for_first():

    from asgi_tools._compat import wait_for_first, aio_sleep

    async def task(name, time):
        await aio_sleep(time)
        return name

    assert 't2' == await wait_for_first(task('t1', 2e-2), task('t2', 1e-2))
