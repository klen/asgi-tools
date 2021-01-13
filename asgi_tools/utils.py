"""ASGI-Tools Utils."""

from functools import wraps
from inspect import iscoroutinefunction, isasyncgenfunction
from multidict import CIMultiDict
from http import cookies


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


def parse_headers(headers: list):
    """Decode the given headers list."""
    if not headers:
        return CIMultiDict()

    return CIMultiDict([[v.decode('latin-1') for v in item] for item in headers])


def parse_cookies(cookie: str):
    """Decode the given cookie header."""
    data = {}

    if cookie:
        for chunk in cookie.split(';'):
            key, _, val = chunk.partition('=')
            data[key.strip()] = cookies._unquote(val.strip())

    return data
