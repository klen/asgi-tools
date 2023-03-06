from __future__ import annotations

from typing import ClassVar, Type  # py38

from http_router import Router as HTTPRouter

from .errors import ASGIError, ASGIInvalidMethodError, ASGINotFoundError


class Router(HTTPRouter):
    """Rebind router errors."""

    NotFoundError: ClassVar[Type[Exception]] = ASGINotFoundError
    RouterError: ClassVar[Type[Exception]] = ASGIError
    InvalidMethodError: ClassVar[Type[Exception]] = ASGIInvalidMethodError
