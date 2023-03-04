from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    Mapping,
    MutableMapping,
    Tuple,
    TypeVar,
    Union,
)

if TYPE_CHECKING:
    from .request import Request

TASGIMessage = Mapping[str, Any]
TASGISend = Callable[[TASGIMessage], Awaitable[None]]
TASGIReceive = Callable[[], Awaitable[TASGIMessage]]
TASGIScope = MutableMapping[str, Any]
TASGIHeaders = List[Tuple[bytes, bytes]]
TASGIApp = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable[Any]]

TJSON = Union[None, bool, int, float, str, List["TJSON"], Mapping[str, "TJSON"]]
TExceptionHandler = Callable[["Request", BaseException], Awaitable]

TV = TypeVar("TV")
TVCallable = TypeVar("TVCallable", bound=Callable)
TVAsyncCallable = TypeVar("TVAsyncCallable", bound=Callable[..., Awaitable])
TVExceptionHandler = TypeVar("TVExceptionHandler", bound=TExceptionHandler)
