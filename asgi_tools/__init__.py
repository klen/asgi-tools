""" ASGI-Tools -- Tools to make ASGI Applications """

__version__ = "0.1.2"
__license__ = "MIT"


class ASGIError(Exception):
    """Base class for ASGI-Tools Errors."""

    pass


class ASGIDecodeError(ASGIError):
    """ASGI-Tools decoding error."""

    pass


DEFAULT_CHARSET = 'utf-8'

from .request import Request  # noqa
from .response import (  # noqa
    parse_response, Response, ResponseHTML, ResponseJSON,
    ResponseText, ResponseRedirect, ResponseError, ResponseStream
)
from .middleware import (  # noqa
    RequestMiddleware, ResponseMiddleware, AppMiddleware, LifespanMiddleware, RouterMiddleware,
    combine, parse_response
)
from .app import App  # noqa
