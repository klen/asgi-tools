# Copyright (c) 2020 Kirill Klenov

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Mapping,
    MutableMapping,
    TypeVar,
)

if TYPE_CHECKING:
    from .request import Request

TASGIMessage = Mapping[str, Any]
TASGISend = Callable[[TASGIMessage], Awaitable[None]]
TASGIReceive = Callable[[], Awaitable[TASGIMessage]]
TASGIScope = MutableMapping[str, Any]
TASGIHeaders = list[tuple[bytes, bytes]]
TASGIApp = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable[Any]]

TJSON = None | bool | int | float | str | list["TJSON"] | Mapping[str, "TJSON"]
TExceptionHandler = Callable[["Request", BaseException], Coroutine[Any, Any, Any]]

TV = TypeVar("TV")
TVCallable = TypeVar("TVCallable", bound=Callable[..., Any])
TVAsyncCallable = TypeVar("TVAsyncCallable", bound=Callable[..., Coroutine[Any, Any, Any]])
TVExceptionHandler = TypeVar("TVExceptionHandler", bound=TExceptionHandler)
