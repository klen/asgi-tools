# Copyright (c) 2020 Kirill Klenov

from __future__ import annotations

from typing import ClassVar

from http_router import Router as HTTPRouter

from .errors import ASGIError, ASGIInvalidMethodError, ASGINotFoundError


class Router(HTTPRouter):
    """Rebind router errors; keep path params raw (ASGI paths are pre-decoded)."""

    NotFoundError: ClassVar[type[Exception]] = ASGINotFoundError
    RouterError: ClassVar[type[Exception]] = ASGIError
    InvalidMethodError: ClassVar[type[Exception]] = ASGIInvalidMethodError

    def __init__(self, *, unquote_params=False, **kwargs):
        # scope["path"] is percent-decoded by the ASGI server; unquoting again double-decodes.
        super().__init__(unquote_params=unquote_params, **kwargs)
