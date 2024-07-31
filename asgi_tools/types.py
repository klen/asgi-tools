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
    Union,
)

if TYPE_CHECKING:
    from .request import Request

TASGIMessage = Mapping[str, Any]
TASGISend = Callable[[TASGIMessage], Awaitable[None]]
TASGIReceive = Callable[[], Awaitable[TASGIMessage]]
TASGIScope = MutableMapping[str, Any]
TASGIHeaders = list[tuple[bytes, bytes]]
TASGIApp = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable[Any]]

TJSON = Union[None, bool, int, float, str, list["TJSON"], Mapping[str, "TJSON"]]
TExceptionHandler = Callable[["Request", BaseException], Coroutine[None, None, Any]]

TV = TypeVar("TV")
TVCallable = TypeVar("TVCallable", bound=Callable)
TVAsyncCallable = TypeVar("TVAsyncCallable", bound=Callable[..., Coroutine])
TVExceptionHandler = TypeVar("TVExceptionHandler", bound=TExceptionHandler)
