from typing import ClassVar, Type  # py37

from http_router import Router as HTTPRouter

from . import ASGIError, ASGIMethodNotAllowed, ASGINotFound


class Router(HTTPRouter):
    """Rebind router errors."""

    NotFound: ClassVar[Type[Exception]] = ASGINotFound
    RouterError: ClassVar[Type[Exception]] = ASGIError
    MethodNotAllowed: ClassVar[Type[Exception]] = ASGIMethodNotAllowed
