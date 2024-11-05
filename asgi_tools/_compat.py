"""Compatability layer."""

from __future__ import annotations

import asyncio
import inspect
from asyncio import create_task, gather, sleep
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED
from contextlib import asynccontextmanager, suppress
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Coroutine,
    Union,
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
    "create_task",
    "json_dumps",
    "json_loads",
    "aiofile_installed",
    "trio_installed",
    "curio_installed",
)

try:
    from asyncio import timeout as asyncio_timeout  # type: ignore[attr-defined]
except ImportError:  # python 39, 310
    from async_timeout import timeout as asyncio_timeout  # type: ignore[no-redef]


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


def aio_sleep(seconds: float = 0) -> Awaitable:
    """Return sleep coroutine."""

    if trio_installed and current_async_library() == "trio":
        return trio_sleep(seconds)  # noqa: ASYNC105

    if curio_installed and current_async_library() == "curio":
        return curio_sleep(seconds)

    return sleep(seconds)


@asynccontextmanager
async def aio_spawn(fn: Callable[..., Awaitable], *args, **kwargs):
    """Spawn a given coroutine."""
    if trio_installed and current_async_library() == "trio":
        async with open_nursery() as tasks:
            tasks.start_soon(fn, *args, **kwargs)
            yield tasks

    elif curio_installed and current_async_library() == "curio":
        task = await curio_spawn(fn, *args, **kwargs)
        yield task
        await task.join()  # type: ignore [union-attr]

    else:
        coro = cast(Coroutine, fn(*args, **kwargs))
        task = create_task(coro)
        yield task
        await task


@asynccontextmanager
async def aio_timeout(timeout: float):  # noqa: ASYNC109
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


async def aio_wait(*aws: Awaitable, strategy: str = ALL_COMPLETED) -> Any:
    """Run the coros concurently, wait for all completed or cancel others.

    Only ALL_COMPLETED, FIRST_COMPLETED are supported.
    """
    if not aws:
        return None

    if trio_installed and current_async_library() == "trio":
        send_channel, receive_channel = open_memory_channel(0)  # type: ignore[var-annotated]

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

    aws = tuple(create_task(aw) if inspect.iscoroutine(aw) else aw for aw in aws)
    done, pending = await asyncio.wait(aws, return_when=strategy)  # type: ignore[type-var]
    if strategy != ALL_COMPLETED:
        for task in pending:
            task.cancel()  # type: ignore[attr-defined]
        await gather(*pending, return_exceptions=True)
        return next(iter(done)).result()  # type: ignore[attr-defined]

    return [t.result() for t in done]  # type: ignore[attr-defined]


async def aio_cancel(task: Union[asyncio.Task, Any]):
    """Cancel asyncio task / trio nursery."""
    if isinstance(task, asyncio.Task):
        return task.cancel()

    if trio_installed and current_async_library() == "trio":
        return task.cancel_scope.cancel()

    if curio_installed and current_async_library() == "curio":
        return await task.cancel()
    return None


async def aio_stream_file(
    filepath: Union[str, Path], chunk_size: int = 32 * 1024
) -> AsyncGenerator[bytes, None]:
    if trio_installed and current_async_library() == "trio":
        async with await trio_open_file(filepath, "rb") as fp:
            while True:
                chunk = cast(bytes, await fp.read(chunk_size))
                if not chunk:
                    break
                yield chunk

    elif curio_installed and current_async_library() == "curio":
        async with curio_open(filepath, "rb") as fp:
            while True:
                chunk = cast(bytes, await fp.read(chunk_size))
                if not chunk:
                    break
                yield chunk

    else:
        if not aiofile_installed:
            raise RuntimeError(  # noqa: TRY003
                "`aiofile` is required to return files with asyncio",
            )

        async with aiofile.AIOFile(filepath, mode="rb") as fp:
            async for chunk in aiofile.Reader(  # type: ignore [assignment]
                fp, chunk_size=chunk_size
            ):
                yield cast(bytes, chunk)


async def trio_jockey(coro: Awaitable, channel):
    """Wait for the given coroutine and send result back to the given channel."""
    await channel.send(await coro)


def json_dumps(content) -> bytes:
    """Emulate orjson."""
    return dumps(  # type: ignore [call-arg]
        content,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def json_loads(obj: Union[bytes, str]) -> TJSON:
    """Emulate orjson."""
    if isinstance(obj, bytes):
        obj = obj.decode("utf-8")
    return loads(obj)


with suppress(ImportError):
    from ujson import dumps as udumps
    from ujson import loads as json_loads  # type: ignore[assignment]

    def json_dumps(content) -> bytes:
        """Emulate orjson."""
        return udumps(content, ensure_ascii=False).encode("utf-8")


with suppress(ImportError):
    from orjson import dumps as json_dumps  # type: ignore[assignment,no-redef]
    from orjson import loads as json_loads  # type: ignore[assignment,no-redef]


# ruff: noqa: PGH003, F811
