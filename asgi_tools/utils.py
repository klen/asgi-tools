"""ASGI-Tools Utils."""

from functools import wraps
from inspect import iscoroutinefunction, isasyncgenfunction
import typing as t

from multidict import CIMultiDict

from ._types import ScopeHeaders


def is_awaitable(fn: t.Callable) -> bool:
    """Check than the given function is awaitable."""
    return iscoroutinefunction(fn) or isasyncgenfunction(fn)


def to_awaitable(fn: t.Callable) -> t.Callable[..., t.Awaitable]:
    """Convert the given function to a coroutine function if it isn't"""
    if is_awaitable(fn):
        return fn

    @wraps(fn)
    async def coro(*args, **kwargs):
        return fn(*args, **kwargs)

    return coro


def parse_headers(headers: ScopeHeaders) -> CIMultiDict:
    """Decode the given headers list."""
    return CIMultiDict([(n.decode('latin-1'), v.decode('latin-1')) for n, v in headers])
