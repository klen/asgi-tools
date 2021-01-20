"""A simple websockets example for ASGI-Tools.

The example requires Jinja2, Websockets installed.
"""

from asgi_tools import App, ResponseWebSocket

from .utils.templates import websockets as template


app = App(debug=True)


@app.route('/')
async def index(request):
    """Render chat page."""
    return template.render()


@app.route('/socket')
async def socket(request):
    """Play to ping pong."""
    ws = ResponseWebSocket(request)
    await ws.accept()
    while ws.connected:
        msg = await ws.receive()
        if msg == 'ping':
            await ws.send('pong')

    return ws
