"""Compatability layer."""

import asyncio
import inspect
import sys
import typing as t
from pathlib import Path
from contextlib import asynccontextmanager
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED

from sniffio import current_async_library

try:
    from orjson import dumps as json_dumps, loads as json_loads  # noqa
except ImportError:
    try:
        from ujson import dumps, loads

        def json_dumps(content) -> bytes:  # type: ignore
            """Emulate orjson."""
            return dumps(content, ensure_ascii=False).encode('utf-8')

    except ImportError:
        from json import dumps, loads  # type: ignore

        def json_dumps(content) -> bytes:  # type: ignore
            """Emulate orjson."""
            return dumps(content, ensure_ascii=False, separators=(',', ':')).encode('utf-8')  # type: ignore # noqa

    def json_loads(obj: t.Union[bytes, str]) -> t.Any:  # type: ignore
        """Emulate orjson."""
        if isinstance(obj, bytes):
            obj = obj.decode('utf-8')
        return loads(obj)


# Python 3.8+
if sys.version_info >= (3, 8):
    create_task = asyncio.create_task

# Python 3.7
else:
    create_task = asyncio.ensure_future


try:
    import aiofile
except ImportError:
    aiofile = None


try:
    import trio

except ImportError:
    trio = None


try:
    import curio

except ImportError:
    curio = None


def aio_sleep(seconds: float = 0) -> t.Awaitable:
    """Return sleep coroutine."""

    if trio and current_async_library() == 'trio':
        return trio.sleep(seconds)

    if curio and current_async_library() == 'curio':
        return curio.sleep(seconds)

    return asyncio.sleep(seconds)


@asynccontextmanager
async def aio_spawn(fn: t.Callable[..., t.Awaitable], *args, **kwargs):
    """Spawn a given coroutine."""
    if trio and current_async_library() == 'trio':
        async with trio.open_nursery() as tasks:
            tasks.start_soon(fn, *args, **kwargs)
            yield tasks

    elif curio and current_async_library() == 'curio':
        task = await curio.spawn(fn, *args, **kwargs)
        yield task
        await task.join()

    else:
        task = create_task(fn(*args, **kwargs))
        yield task
        await asyncio.gather(task)


async def aio_wait(*aws: t.Awaitable, strategy: str = ALL_COMPLETED) -> t.Any:
    """Run the coros concurently, wait for all completed or cancel others.

    Only ALL_COMPLETED, FIRST_COMPLETED are supported.
    """
    if not aws:
        return

    if trio and current_async_library() == 'trio':

        send_channel, receive_channel = trio.open_memory_channel(0)

        async with trio.open_nursery() as n:
            [n.start_soon(trio_jockey, aw, send_channel) for aw in aws]
            results = []
            for _ in aws:
                results.append(await receive_channel.receive())
                if strategy == FIRST_COMPLETED:
                    n.cancel_scope.cancel()
                    return results[0]

            return results

    if curio and current_async_library() == 'curio':
        wait = all if strategy == ALL_COMPLETED else any
        async with curio.TaskGroup(wait=wait) as g:
            [await g.spawn(aw) for aw in aws]

        return g.results if strategy == ALL_COMPLETED else g.result

    aws = tuple(create_task(aw) if inspect.iscoroutine(aw) else aw for aw in aws)
    done, pending = await asyncio.wait(aws, return_when=strategy)
    if strategy != ALL_COMPLETED:
        [task.cancel() for task in pending]
        await asyncio.gather(*pending, return_exceptions=True)
        return list(done)[0].result()

    return [t.result() for t in done]


async def aio_cancel(task: t.Union[asyncio.Task, t.Any]):
    """Cancel asyncio task / trio nursery."""
    if isinstance(task, asyncio.Task):
        return task.cancel()

    if trio and current_async_library() == 'trio':
        return task.cancel_scope.cancel()

    if curio and current_async_library() == 'curio':
        return await task.cancel()


async def aio_stream_file(filepath: t.Union[str, Path], chunk_size: int = 32 * 1024) -> t.AsyncGenerator[bytes, None]:  # noqa

    if trio and current_async_library() == 'trio':
        async with await trio.open_file(filepath, 'rb') as fp:
            while True:
                chunk = await fp.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    elif curio and current_async_library() == 'curio':
        async with curio.aopen(filepath, 'rb') as fp:
            while True:
                chunk = await fp.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    else:
        if aiofile is None:
            raise RuntimeError('`aiofile` is required to return files with asyncio')

        async with aiofile.AIOFile(filepath, mode='rb') as fp:
            async for chunk in aiofile.Reader(fp, chunk_size=chunk_size):
                yield chunk


async def trio_jockey(coro: t.Awaitable, channel):
    """Wait for the given coroutine and send result back to the given channel."""
    await channel.send(await coro)
