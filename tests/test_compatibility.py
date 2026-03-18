from __future__ import annotations

from asgi_tools._compat import FIRST_COMPLETED, aio_sleep, aio_spawn, aio_wait


async def test_aio_sleep():

    await aio_sleep(1e-2)


async def test_aio_spawn():

    side_effects = {}

    async def task(name):
        side_effects[name] = True

    async with aio_spawn(task, "tests"):
        await aio_sleep(1e-2)

    assert side_effects["tests"] is True


async def test_aio_wait():

    async def task(name, time):
        await aio_sleep(time)
        return name

    assert await aio_wait(task("t1", 2e-2), task("t2", 1e-2), strategy=FIRST_COMPLETED) == "t2"
