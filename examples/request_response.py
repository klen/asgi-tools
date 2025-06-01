"""The example shows how to use `asgi_tools.Request`."""

from __future__ import annotations

from asgi_tools import Request, Response

from .utils.templates import request_info as template


async def app(scope, receive, send):
    """Parse and return request data."""
    if scope["type"] != "http":
        return None

    # Parse the given scope
    request = Request(scope, receive, send)

    # Render the page
    body = template.render(
        # Get full URL
        url=request.url,
        charset=request.charset,
        # Get headers
        headers=request.headers,
        # Get query params
        query=request.url.query,
        # Get cookies
        cookies=request.cookies,
        # Get a decoded request body
        text=await request.text(),
        # ASGI Scope
        scope=request.scope,
    )
    response = Response(body, content_type="text/html")
    return await response(scope, receive, send)
