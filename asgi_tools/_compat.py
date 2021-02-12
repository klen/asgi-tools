"""Compatability layer."""

import asyncio
import inspect
import sys
import typing as t
from contextlib import asynccontextmanager

from sniffio import current_async_library


# Python 3.8+
if sys.version_info >= (3, 8):
    from functools import cached_property  # noqa
    from typing import TypedDict  # noqa

    create_task = asyncio.create_task

# Python 3.7
else:
    from cached_property import cached_property  # noqa
    from typing_extensions import TypedDict  # noqa

    create_task = asyncio.ensure_future


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
            tasks.start_soon(fn, *args, **kwargs)
            yield tasks

    else:
        yield create_task(fn(*args, **kwargs))


async def wait_for_first(*aws: t.Awaitable) -> t.Any:
    """Run the coros concurently, wait for first completed and cancel others."""
    if not aws:
        return

    if trio is None or current_async_library() == 'asyncio':
        aws = tuple(create_task(aw) if inspect.iscoroutine(aw) else aw for aw in aws)
        (done,), pending = await asyncio.wait(aws, return_when=asyncio.FIRST_COMPLETED)
        [task.cancel() for task in pending]
        return done.result()

    send_channel, receive_channel = trio.open_memory_channel(0)

    async with trio.open_nursery() as n:
        [n.start_soon(trio_jockey, aw, send_channel) for aw in aws]
        result = await receive_channel.receive()
        n.cancel_scope.cancel()
        return result


def cancel_task(task: t.Union[asyncio.Task, t.Any]):
    """Cancel asyncio task / trio nursery."""
    if isinstance(task, asyncio.Task):
        return task.cancel()

    task.cancel_scope.cancel()


async def trio_jockey(coro: t.Awaitable, channel):
    """Wait for the given coroutine and send result back to the given channel."""
    await channel.send(await coro)
