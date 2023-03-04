from __future__ import annotations


class ASGIError(Exception):
    """Base class for ASGI-Tools Errors."""


class ASGIConnectionClosedError(ASGIError):
    """ASGI-Tools connection closed error."""


class ASGIDecodeError(ASGIError, ValueError):
    """ASGI-Tools decoding error."""


class ASGINotFoundError(ASGIError):
    """Raise when http handler not found."""


class ASGIInvalidMethodError(ASGIError):
    """Raise when http method not found."""


class ASGIInvalidMessageError(ASGIError):
    """Raise when unexpected message received."""
