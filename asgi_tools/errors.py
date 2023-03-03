class ASGIError(Exception):
    """Base class for ASGI-Tools Errors."""


class ASGIConnectionClosed(ASGIError):
    """ASGI-Tools connection closed error."""


class ASGIDecodeError(ASGIError, ValueError):
    """ASGI-Tools decoding error."""


class ASGINotFound(ASGIError):
    """Raise when http handler not found."""


class ASGIMethodNotAllowed(ASGIError):
    """Raise when http method not found."""
