from typing import (TYPE_CHECKING, Any, Awaitable, Callable, List, Mapping, MutableMapping, Tuple,
                    TypeVar, Union)

if TYPE_CHECKING:
    from .response import Response

TVFn = TypeVar("TVFn", bound=Callable)

TASGIMessage = Mapping[str, Any]
TASGISend = Callable[[TASGIMessage], Awaitable[None]]
TASGIReceive = Callable[[], Awaitable[TASGIMessage]]
TASGIScope = MutableMapping[str, Any]
TASGIHeaders = List[Tuple[bytes, bytes]]
TASGIApp = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable[Any]]

TResponseApp = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable["Response"]]
TResponseContent = Union[bytes, str]
TMiddleware = Callable[[TASGIScope, TASGIReceive, TASGISend], Awaitable[Any]]
TJSON = Union[None, bool, int, float, str, List["TJSON"], Mapping[str, "TJSON"]]
