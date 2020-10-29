from asyncio import iscoroutinefunction
from functools import wraps


def to_coroutine(fn):
    """Convert the given function to a coroutine function if it isn't"""
    if iscoroutinefunction(fn):
        return fn

    @wraps(fn)
    async def coro(*args, **kwargs):
        return fn(*args, **kwargs)

    return coro
