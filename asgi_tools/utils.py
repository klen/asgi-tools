"""ASGI-Tools Utils."""

from functools import wraps
from inspect import iscoroutinefunction, isasyncgenfunction


try:
    import aiofile
except ImportError:
    aiofile = None


try:
    import trio
except ImportError:
    trio = None


def is_awaitable(fn):
    """Check than the given function is awaitable."""
    return iscoroutinefunction(fn) or isasyncgenfunction(fn)


def to_awaitable(fn):
    """Convert the given function to a coroutine function if it isn't"""
    if is_awaitable(fn):
        return fn

    @wraps(fn)
    async def coro(*args, **kwargs):
        return fn(*args, **kwargs)

    return coro
