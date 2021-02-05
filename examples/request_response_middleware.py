"""The example shows how to use `asgi_tools.Request`."""

from asgi_tools import RequestMiddleware, ResponseMiddleware


async def request_as_json(request, receive, send):
    """Parse and return request data."""

    # Render the page as JSON
    return {
        "url": str(request.url),
        "charset": request.charset,
        "content_type": request.content_type,
        "headers": dict(request.headers),
        "query": dict(request.url.query),
        "cookies": dict(request.cookies),
        "content": await request.text()
    }


app = ResponseMiddleware(RequestMiddleware(request_as_json))
