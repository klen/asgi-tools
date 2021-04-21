"""A simple SSE (server side events) example for ASGI-Tools."""

import time
import asyncio

from asgi_tools import App, ResponseSSE


app = App(debug=True)


@app.route('/')
async def index(request):
    """Render main page."""
    return """
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css">
    <div class="container p-3">
        <h1 class="mb-4"> ASGI Tools Server Side Events example </h1>
        <p>Open debugger and check network to sse eventstream.</p>
        <h3>Events from server</h3>
        <div class="mb-4 p-2" id="messages"
             style="background: #ccc; height: 30em; overflow-y: scroll;"></div>
        <button class="btn btn-danger" id="disconnect">Disconnect</button>
    </div>
    <script>
        const messages = document.querySelector('#messages'),
              sseSource = new EventSource("/sse");

        document.querySelector('#disconnect').addEventListener('click', function () {
            sseSource.close();
            showMessage('Stream is disconnected. Reload the page to reconnect.');
        });

        const showMessage = (text) => {
            let message = document.createElement('p');
            message.innerHTML = text;
            messages.appendChild(message);
            messages.scrollTop = messages.scrollHeight;
        };

        sseSource.onmessage = function (event) {
            showMessage("message: " + event.data);
        };

        sseSource.addEventListener('ping', function (event) {
            showMessage("ping: " + event.data);
        });
    </script>
"""


@app.route('/sse')
async def stream_events(request):
    """An example events stream."""

    async def stream():
        events = 20
        # Send event as text
        yield "data: start stream"

        while events:
            # Send event as dict (will be converted to text)
            yield {
                "data": time.time(),
                "event": "ping",
            }
            events -= 1
            await asyncio.sleep(1)

        yield "data: stream is over"

    return ResponseSSE(stream())
