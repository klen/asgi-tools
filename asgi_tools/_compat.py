"""Compatability layer."""

import asyncio
import typing as t
from contextlib import asynccontextmanager

from sniffio import current_async_library


try:
    import aiofile
except ImportError:
    aiofile = None


try:
    import trio
except ImportError:
    trio = None


def aio_sleep(seconds: float = 0) -> t.Awaitable:
    """Return sleep coroutine."""
    if trio and current_async_library() == 'trio':
        return trio.sleep(seconds)

    return asyncio.sleep(seconds)


@asynccontextmanager
async def aio_spawn(fn: t.Callable[..., t.Awaitable], *args, **kwargs):
    """Spawn a given coroutine."""
    if trio and current_async_library() == 'trio':
        async with trio.open_nursery() as tasks:
            yield tasks.start_soon(fn, *args, **kwargs)

    else:
        yield asyncio.create_task(fn(*args, **kwargs))


async def wait_for_first(*coros: t.Awaitable) -> t.Any:
    """Run the coros concurently, wait for first completed and cancel others."""
    if not coros:
        return

    if trio and current_async_library() == 'trio':
        send_channel, receive_channel = trio.open_memory_channel(0)

        async with trio.open_nursery() as n:
            [n.start_soon(trio_jockey, coro, send_channel) for coro in coros]
            result = await receive_channel.receive()
            n.cancel_scope.cancel()
            return result

    (done,), pending = await asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
    [task.cancel() for task in pending]
    return done.result()


async def trio_jockey(coro: t.Awaitable, channel):
    """Wait for the given coroutine and send result back to the given channel."""
    await channel.send(await coro)
