""" ASGI-Tools -- Tools to make ASGI Applications """

__version__ = "0.5.0"
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
    Response, ResponseHTML, ResponseJSON, ResponseText,
    ResponseRedirect, ResponseError, ResponseStream, ResponseFile, parse_response
)
from .middleware import (  # noqa
    RequestMiddleware, ResponseMiddleware, AppMiddleware, LifespanMiddleware,
    RouterMiddleware, StaticFilesMiddleware, combine
)
from .app import App  # noqa
