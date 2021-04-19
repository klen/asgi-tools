"""Simplest application."""

from asgi_tools import App, ResponseHTML

app = App()


@app.route('/')
async def hello(request):
    """Render 'Hello, World!' as html response."""
    assert request.url
    assert request.headers
    return ResponseHTML('Hello, World!')
