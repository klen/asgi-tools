"""ASGI Types."""

import typing as t


Message = t.MutableMapping[str, t.Any]
Send = t.Callable[[Message], t.Awaitable[t.Any]]
Receive = t.Callable[[], t.Awaitable[Message]]
Scope = t.MutableMapping[str, t.Any]
ScopeHeaders = t.List[t.Tuple[bytes, bytes]]
ASGIApp = t.Callable[[Scope, Receive, Send], t.Awaitable]
JSONType = t.Union[str, int, float, bool, None, t.Dict[str, t.Any], t.List[t.Any]]

ResponseContent = t.Union[str, bytes]
