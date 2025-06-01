""" ASGI-Tools -- Tools to make ASGI Applications """
from __future__ import annotations

from http_router import InvalidMethodError, NotFoundError

from .app import App
from .errors import ASGIConnectionClosedError, ASGIError, ASGIInvalidMethodError, ASGINotFoundError
from .middleware import (
    BackgroundMiddleware,
    LifespanMiddleware,
    RequestMiddleware,
    ResponseMiddleware,
    RouterMiddleware,
    StaticFilesMiddleware,
)
from .request import Request
from .response import (
    Response,
    ResponseError,
    ResponseFile,
    ResponseHTML,
    ResponseJSON,
    ResponseRedirect,
    ResponseSSE,
    ResponseStream,
    ResponseText,
    ResponseWebSocket,
    parse_response,
)
from .view import HTTPView

__all__ = (
    # Errors
    "ASGIConnectionClosedError",
    "ASGIError",
    "ASGIInvalidMethodError",
    "ASGINotFoundError",
    # App/handlers
    "App",
    # Middleware
    "BackgroundMiddleware",
    "HTTPView",
    "InvalidMethodError",
    "LifespanMiddleware",
    "NotFoundError",
    # Request/Response
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
    # Utils
    "parse_response",
)
