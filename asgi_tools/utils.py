"""ASGI-Tools Utils."""

from __future__ import annotations

import re
from functools import wraps
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import TYPE_CHECKING, Callable, Coroutine, overload
from urllib.parse import unquote_to_bytes

from multidict import CIMultiDict

from .constants import BASE_ENCODING

if TYPE_CHECKING:
    from .types import TV, TASGIHeaders, TVAsyncCallable


def is_awaitable(fn: Callable) -> bool:
    """Check than the given function is awaitable."""
    return iscoroutinefunction(fn) or isasyncgenfunction(fn)


@overload
def to_awaitable(fn: TVAsyncCallable) -> TVAsyncCallable: ...


@overload
def to_awaitable(fn: Callable[..., TV]) -> Callable[..., Coroutine[None, None, TV]]: ...


def to_awaitable(fn: Callable):
    """Convert the given function to a coroutine function if it isn't"""
    if is_awaitable(fn):
        return fn

    @wraps(fn)
    async def coro(*args, **kwargs):
        return fn(*args, **kwargs)

    return coro


def parse_headers(headers: TASGIHeaders) -> CIMultiDict:
    """Decode the given headers list."""
    return CIMultiDict(
        [(n.decode(BASE_ENCODING), v.decode(BASE_ENCODING)) for n, v in headers],
    )


OPTION_HEADER_PIECE_RE = re.compile(
    r"""
    \s*,?\s*  # newlines were replaced with commas
    (?P<key>
        "[^"\\]*(?:\\.[^"\\]*)*"  # quoted string
    |
        [^\s;,=*]+  # token
    )
    (?:\*(?P<count>\d+))?  # *1, optional continuation index
    \s*
    (?:  # optionally followed by =value
        (?:  # equals sign, possibly with encoding
            \*\s*=\s*  # * indicates extended notation
            (?:  # optional encoding
                (?P<encoding>[^\s]+?)
                '(?P<language>[^\s]*?)'
            )?
        |
            =\s*  # basic notation
        )
        (?P<value>
            "[^"\\]*(?:\\.[^"\\]*)*"  # quoted string
        |
            [^;,]+  # token
        )?
    )?
    \s*;?
    """,
    flags=re.VERBOSE,
)


def parse_options_header(value: str) -> tuple[str, dict[str, str]]:
    """Parse the given content disposition header."""

    options: dict[str, str] = {}
    if not value:
        return "", options

    if ";" not in value:
        return value, options

    ctype, rest = value.split(";", 1)
    while rest:
        match = OPTION_HEADER_PIECE_RE.match(rest)
        if not match:
            break

        option, count, encoding, _, value = match.groups()
        if value is not None:
            if encoding is not None:
                value = unquote_to_bytes(value).decode(encoding)

            if count:
                value = options.get(option, "") + value

        options[option] = value.strip('" ').replace("\\\\", "\\").replace('\\"', '"')
        rest = rest[match.end() :]

    return ctype, options
