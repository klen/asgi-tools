""" ASGI-Tools -- Tools to make ASGI Applications """

__version__ = "0.64.1"
__license__ = "MIT"

import logging

asgi_logger: logging.Logger = logging.getLogger("asgi-tools")


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


DEFAULT_CHARSET: str = "utf-8"

from http_router import MethodNotAllowed, NotFound  # noqa

from .app import App, HTTPView  # noqa
from .middleware import RequestMiddleware  # noqa
from .middleware import (LifespanMiddleware, ResponseMiddleware, RouterMiddleware,
                         StaticFilesMiddleware)
from .request import Request  # noqa
from .response import ResponseFile  # noqa
from .response import (Response, ResponseError, ResponseHTML, ResponseJSON, ResponseRedirect,
                       ResponseSSE, ResponseStream, ResponseText, ResponseWebSocket, parse_response)

__all__ = (
    "App",
    "HTTPView",
    "LifespanMiddleware",
    "MethodNotAllowed",
    "NotFound",
    "Request",
    "RequestMiddleware",
    "Response",
    "ResponseError",
    "ResponseFile",
    "ResponseHTML",
    "ResponseJSON",
    "ResponseMiddleware",
    "ResponseRedirect",
    "ResponseSSE",
    "ResponseStream",
    "ResponseText",
    "ResponseWebSocket",
    "RouterMiddleware",
    "StaticFilesMiddleware",
    "parse_response",
)
