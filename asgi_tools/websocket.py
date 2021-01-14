"""ASGI Websockets."""

from enum import Enum

from . import ASGIConnectionClosed
from .request import Connection


def parse_msg(msg, charset=None):
    """Prepare websocket message."""
    return msg.get('text') or msg.get('bytes').decode(charset)


class WebSocket(Connection):
    """Represent WebSocket."""

    class STATES(Enum):
        """Represent websocket states."""

        connecting = 0
        connected = 1
        disconnected = 2

    def __init__(self, scope, receive, send):
        """Initialize the websocket."""
        super(WebSocket, self).__init__(scope, receive, send)
        self.state = self.STATES.connecting
        self.partner_state = self.STATES.connecting

    @property
    def connected(self):
        return self.state == self.STATES.connected

    async def connect(self):
        """Wait for connect message."""
        if self.partner_state == self.STATES.connecting:
            msg = await self._receive()
            assert msg.get('type') == 'websocket.connect'
            self.partner_state = self.STATES.connected

        return self.partner_state == self.STATES.connected

    async def receive(self, raw=False):
        """Receive and decode messages from a client."""
        if self.partner_state == self.STATES.disconnected:
            raise ASGIConnectionClosed('Cannot receive once a connection has been disconnected.')

        if self.partner_state == self.STATES.connecting:
            await self.connect()
            return await self.receive(raw=raw)

        msg = await self._receive()
        if msg['type'] == 'websocket.disconnect':
            self.partner_state == self.STATES.disconnected
            raise ASGIConnectionClosed('Connection has been disconnected.')

        return raw and msg or parse_msg(msg, charset=self.charset)

    def send(self, msg, type='websocket.send'):
        """Send messages to a client.."""
        if self.state == self.STATES.disconnected:
            raise ASGIConnectionClosed('Cannot send once the connection has been disconnected.')

        if not isinstance(msg, dict):
            msg = {'type': type, (isinstance(msg, str) and 'text' or 'bytes'): msg}

        return self._send(msg)

    async def accept(self, **params):
        """Sent by the application when it wishes to accept an incoming connection."""
        if self.partner_state == self.STATES.connecting:
            await self.connect()

        await self.send({'type': 'websocket.accept', **params})
        self.state = self.STATES.connected

    async def close(self, code=1000):
        """Sent by the application to tell the server to close the connection."""
        await self.send({'type': 'websocket.close', 'code': code})
        self.state = self.STATES.disconnected
