"""A simple websockets example for ASGI-Tools.

The example requires Jinja2, Websockets installed.
"""

from asgi_tools import App

from asgi_tools.tests import aio_sleep
from .utils.templates import websockets as template


app = App()
del app.exception_handlers[Exception]


@app.route('/')
async def chat(request):
    """Render chat page."""
    return template.render()


@app.route('/socket')
async def socket(ws):
    await ws.accept()

    while ws.connected:
        msg = await ws.receive()
        if msg == 'ping':
            await ws.send('pong')
