"""ASGI Types."""

from typing import Any, Awaitable, Callable, Dict, List, MutableMapping, Tuple, TypeVar, Union

Message = MutableMapping[str, Any]
Send = Callable[[Message], Awaitable[Any]]
Receive = Callable[[], Awaitable[Message]]
Scope = MutableMapping[str, Any]
ScopeHeaders = List[Tuple[bytes, bytes]]
JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable]

ResponseContent = Union[str, bytes]
F = TypeVar("F", bound=Callable)
DecoratedCallable = TypeVar("DecoratedCallable", bound=Callable)
