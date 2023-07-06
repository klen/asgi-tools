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
    "InvalidMethodError",
    "NotFoundError",
    # App/handlers
    "App",
    "HTTPView",
    # Request/Response
    "Request",
    "Response",
    "ResponseError",
    "ResponseFile",
    "ResponseHTML",
    "ResponseJSON",
    "ResponseRedirect",
    "ResponseSSE",
    "ResponseStream",
    "ResponseText",
    "ResponseWebSocket",
    # Middleware
    "BackgroundMiddleware",
    "LifespanMiddleware",
    "RequestMiddleware",
    "ResponseMiddleware",
    "RouterMiddleware",
    "StaticFilesMiddleware",
    # Utils
    "parse_response",
)
