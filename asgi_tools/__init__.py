""" ASGI-Tools -- Tools to make ASGI Applications """

__version__ = "0.0.6"
__license__ = "MIT"


class ASGIError(Exception):
    """Base class for ASGI-Tools Errors."""

    pass


class ASGIDecodeError(ASGIError):
    """ASGI-Tools decoding error."""

    pass


SUPPORTED_SCOPES = {'http', 'websocket'}
DEFAULT_CHARSET = 'utf-8'


from .request import Request  # noqa
from .response import Response, HTMLResponse, JSONResponse, PlainTextResponse  # noqa
from .middleware import (  # noqa
    RequestMiddleware, ResponseMiddleware, AppMiddleware, LifespanMiddleware, RouterMiddleware,
    combine, parse_response
)
