from __future__ import annotations

from typing import ClassVar

from http_router import Router as HTTPRouter

from .errors import ASGIError, ASGIInvalidMethodError, ASGINotFoundError


class Router(HTTPRouter):
    """Rebind router errors."""

    NotFoundError: ClassVar[type[Exception]] = ASGINotFoundError
    RouterError: ClassVar[type[Exception]] = ASGIError
    InvalidMethodError: ClassVar[type[Exception]] = ASGIInvalidMethodError
