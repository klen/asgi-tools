from http import cookies, HTTPStatus
from json import dumps

from multidict import CIMultiDict

from . import DEFAULT_CHARSET


# TODO: Stream/File responses


class Response:

    charset = DEFAULT_CHARSET

    def __init__(
            self, content=None, status_code=HTTPStatus.OK.value, headers=None, content_type=None):
        self.content = content
        self.status_code = status_code
        self._headers = CIMultiDict(headers or {})
        self.cookies = cookies.SimpleCookie()
        if content_type:
            if content_type.startswith('text/'):
                content_type = f"{content_type}; charset={self.charset}"

            self._headers['content-type'] = content_type

    def __iter__(self):
        body = self.body
        self._headers['content-length'] = str(len(body))
        yield {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.headers,
        }
        yield {"type": "http.response.body", "body": self.body}

    def __str__(self):
        return f"{self.status_code}"

    def __repr__(self):
        return f"<Response '{ self }'"

    async def __call__(self, scope, receive, send):
        for message in self:
            await send(message)

    @property
    def body(self):
        if self.content is None:
            return b""

        if isinstance(self.content, bytes):
            return self.content

        return self.content.encode(self.charset)

    @property
    def headers(self):
        headers = [
            (key.lower().encode('latin-1'), val.encode('latin-1'))
            for key, val in self._headers.items()
        ]
        if self.cookies:
            val = self.cookies.output(header='').strip()
            headers.append((b"set-cookie", val.encode('latin-1')))
        return headers


class HTMLResponse(Response):

    def __init__(self, *args, **kwargs):
        kwargs['content_type'] = 'text/html'
        super().__init__(*args, **kwargs)


class PlainTextResponse(Response):

    def __init__(self, *args, **kwargs):
        kwargs['content_type'] = 'text/plain'
        super().__init__(*args, **kwargs)


class JSONResponse(Response):

    def __init__(self, *args, **kwargs):
        kwargs['content_type'] = 'application/json'
        super().__init__(*args, **kwargs)

    @property
    def body(self):
        return dumps(self.content, ensure_ascii=False, allow_nan=False).encode(self.charset)
