"""ASGI-Tools Utils."""

import asyncio as aio
from functools import wraps
from inspect import iscoroutinefunction, isasyncgenfunction
import typing as t

from multidict import CIMultiDict
from sniffio import current_async_library

from .types import ScopeHeaders


try:
    import aiofile  # type: ignore
except ImportError:
    aiofile = None


try:
    import trio  # type: ignore
except ImportError:
    trio = None


F = t.TypeVar('F', bound=t.Callable[..., t.Any])


def aio_sleep(seconds: float) -> t.Awaitable:
    """Return sleep coroutine."""
    if trio and current_async_library() == 'trio':
        return trio.sleep(seconds)

    return aio.sleep(seconds)


def is_awaitable(fn: t.Callable) -> bool:
    """Check than the given function is awaitable."""
    return iscoroutinefunction(fn) or isasyncgenfunction(fn)


def to_awaitable(fn: F) -> t.Union[F, t.Callable[..., t.Coroutine]]:
    """Convert the given function to a coroutine function if it isn't"""
    if is_awaitable(fn):
        return fn

    @wraps(fn)
    async def coro(*args, **kwargs):
        return fn(*args, **kwargs)

    return coro


def parse_headers(headers: ScopeHeaders) -> CIMultiDict[str]:
    """Decode the given headers list."""
    return CIMultiDict(
        [tuple([n.decode('latin-1'), v.decode('latin-1')]) for n, v in headers])  # type: ignore
