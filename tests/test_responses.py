async def test_response():
    from asgi_tools import Response, parse_response

    response = Response("Content", content_type='text/html')
    response.cookies['session'] = 'test-session'
    response.cookies['session']['path'] = '/'
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.get_headers() == [
        (b"content-type", b"text/html; charset=utf-8"),
        (b'set-cookie', b'session=test-session; Path=/'),
    ]
    messages = [m for m in response]
    assert messages
    assert messages[0] == {
        'headers': [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'set-cookie', b'session=test-session; Path=/'),
            (b'content-length', b'7'),
        ],
        'status': 200,
        'type': 'http.response.start'
    }
    assert messages[1] == {'body': b'Content', 'type': 'http.response.body'}

    response = await parse_response({'test': 'passed'})
    assert response.status_code == 200
    assert response.get_headers() == [(b'content-type', b'application/json')]
    assert list(response)[1] == {'body': b'{"test": "passed"}', 'type': 'http.response.body'}

    response = await parse_response((500,))
    assert response.status_code == 500


async def test_html_response():
    from asgi_tools import HTMLResponse

    response = HTMLResponse("Content")
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.get_headers() == [
        (b"content-type", b"text/html; charset=utf-8"),
    ]


async def test_text_response():
    from asgi_tools import PlainTextResponse

    response = PlainTextResponse("Content")
    assert response.body == b"Content"
    assert response.status_code == 200
    assert response.get_headers() == [
        (b"content-type", b"text/plain; charset=utf-8"),
    ]


async def test_json_response():
    from asgi_tools import JSONResponse

    response = JSONResponse([1, 2, 3])
    assert response.body == b"[1, 2, 3]"
    assert response.status_code == 200
    assert response.get_headers() == [
        (b"content-type", b"application/json"),
    ]


async def test_redirect_response():
    from asgi_tools import RedirectResponse

    response = RedirectResponse('/logout')
    assert response.body == b""
    assert response.status_code == 307
    assert response.get_headers() == [
        (b"location", b"/logout"),
    ]
