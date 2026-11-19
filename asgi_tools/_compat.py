# Copyright (c) 2020 Kirill Klenov

"""Compatibility layer."""

from __future__ import annotations

import asyncio
import inspect
from asyncio import create_task, ensure_future, gather, sleep
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED
from contextlib import asynccontextmanager, suppress
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    cast,
)

if TYPE_CHECKING:
    from pathlib import Path

    from .types import TJSON


from json import dumps, loads

from sniffio import current_async_library

__all__ = (
    "aio_cancel",
    "aio_sleep",
    "aio_spawn",
    "aio_stream_file",
    "aio_wait",
    "aiofile_installed",
    "create_task",
    "curio_installed",
    "json_dumps",
    "json_loads",
    "trio_installed",
)

from asyncio import timeout as asyncio_timeout

aiofile_installed = False
with suppress(ImportError):
    import aiofile

    aiofile_installed = True


trio_installed = False
with suppress(ImportError):
    from trio import TooSlowError, open_memory_channel, open_nursery
    from trio import fail_after as trio_fail_after
    from trio import open_file as trio_open_file
    from trio import sleep as trio_sleep

    trio_installed = True


curio_installed = False
with suppress(ImportError):
    from curio import TaskGroup as CurioTaskGroup
    from curio import TaskTimeout
    from curio import aopen as curio_open
    from curio import sleep as curio_sleep
    from curio import spawn as curio_spawn
    from curio import timeout_after as curio_fail_after

    curio_installed = True


def aio_sleep(seconds: float = 0) -> Awaitable[Any]:
    """Return sleep coroutine."""

    if trio_installed and current_async_library() == "trio":
        return cast("Awaitable[Any]", trio_sleep(seconds))  # noqa: ASYNC105

    if curio_installed and current_async_library() == "curio":
        return cast("Awaitable[Any]", curio_sleep(seconds))

    return sleep(seconds)


@asynccontextmanager
async def aio_spawn(
    fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> AsyncGenerator[Any, None]:
    """Spawn a given coroutine."""
    if trio_installed and current_async_library() == "trio":
        async with open_nursery() as tasks:
            tasks.start_soon(fn, *args, **kwargs)
            yield tasks

    elif curio_installed and current_async_library() == "curio":
        task = await curio_spawn(fn, *args, **kwargs)
        yield task
        await task.join()

    else:
        coro = cast("Coroutine[Any, Any, Any]", fn(*args, **kwargs))
        task = create_task(coro)
        yield task
        await task


@asynccontextmanager
async def aio_timeout(timeout: float) -> AsyncGenerator[None, None]:
    """Fail after the given timeout."""
    if not timeout:
        yield
        return

    if trio_installed and current_async_library() == "trio":
        try:
            with trio_fail_after(timeout):
                yield

        except TooSlowError:
            raise TimeoutError(f"{timeout}s.") from None

    elif curio_installed and current_async_library() == "curio":
        try:
            async with curio_fail_after(timeout):
                yield

        except TaskTimeout:
            raise TimeoutError(f"{timeout}s.") from None

    else:
        async with asyncio_timeout(timeout):
            yield


async def aio_wait(*aws: Awaitable[Any], strategy: str = ALL_COMPLETED) -> Any:
    """Run the coros concurrently, wait for all completed or cancel others.

    Only ALL_COMPLETED, FIRST_COMPLETED are supported.
    """
    if not aws:
        return None

    if trio_installed and current_async_library() == "trio":
        send_channel, receive_channel = open_memory_channel(0)

        async with open_nursery() as n:
            for aw in aws:
                n.start_soon(trio_jockey, aw, send_channel)

            results = []
            for _ in aws:
                results.append(await receive_channel.receive())
                if strategy == FIRST_COMPLETED:
                    n.cancel_scope.cancel()
                    return results[0]

            return results

    if curio_installed and current_async_library() == "curio":
        wait = all if strategy == ALL_COMPLETED else any
        async with CurioTaskGroup(wait=wait) as g:
            [await g.spawn(aw) for aw in aws]

        return g.results if strategy == ALL_COMPLETED else g.result

    tasks = tuple(create_task(aw) if inspect.iscoroutine(aw) else ensure_future(aw) for aw in aws)
    done, pending = await asyncio.wait(tasks, return_when=strategy)
    if strategy != ALL_COMPLETED:
        for task in pending:
            task.cancel()
        await gather(*pending, return_exceptions=True)
        return next(iter(done)).result()

    return [t.result() for t in done]


async def aio_cancel(task: Any) -> None:
    """Cancel asyncio task / trio nursery."""
    if isinstance(task, asyncio.Task):
        task.cancel()
        return

    if trio_installed and current_async_library() == "trio":
        task.cancel_scope.cancel()
        return

    if curio_installed and current_async_library() == "curio":
        await task.cancel()


async def aio_stream_file(
    filepath: Path | str, chunk_size: int = 32 * 1024
) -> AsyncGenerator[bytes, None]:
    if trio_installed and current_async_library() == "trio":
        async with await trio_open_file(filepath, "rb") as fp:
            while True:
                chunk = await fp.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    elif curio_installed and current_async_library() == "curio":
        async with curio_open(filepath, "rb") as fp:
            while True:
                chunk = cast("bytes", await fp.read(chunk_size))
                if not chunk:
                    break
                yield chunk

    else:
        if not aiofile_installed:
            raise RuntimeError(
                "`aiofile` is required to return files with asyncio",
            )

        async with aiofile.AIOFile(filepath, mode="rb") as fp:
            async for data in aiofile.Reader(fp, chunk_size=chunk_size):
                yield cast("bytes", data)


async def trio_jockey(coro: Awaitable[Any], channel: Any) -> None:
    """Wait for the given coroutine and send result back to the given channel."""
    await channel.send(await coro)


def json_dumps(content: Any) -> bytes:
    """Emulate orjson."""
    return dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def json_loads(obj: bytes | str) -> TJSON:
    """Emulate orjson."""
    if isinstance(obj, bytes):
        obj = obj.decode("utf-8")
    return cast("TJSON", loads(obj))


with suppress(ImportError):
    from orjson import OPT_NON_STR_KEYS
    from orjson import dumps as orjson_dumps
    from orjson import loads as orjson_loads

    def json_dumps(content: Any) -> bytes:
        """Emulate orjson."""
        return orjson_dumps(content, default=str, option=OPT_NON_STR_KEYS)

    def json_loads(obj: bytes | str) -> TJSON:
        """Emulate orjson."""
        return cast("TJSON", orjson_loads(obj))
