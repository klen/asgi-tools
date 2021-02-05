"""Simple Test Client."""


async def test_client(app, client):
    res = await client.get('/')
    assert res
    assert res.status_code == 200
    assert res.headers
    assert res.headers['content-type']
    assert res.headers['content-length'] == '2'
    text = await res.text()
    assert text == 'OK'

    @app.route('/test')
    async def test(request):
        data = await request.data()
        if not isinstance(data, str):
            data = dict(data)

        return {
            'query': dict(request.url.query),
            "headers": {**request.headers},
            "cookies": dict(request.cookies),
            "data": data,
        }

    res = await client.patch('/test')
    assert res.status_code == 200
    json = await res.json()
    assert json == {
        'query': {},
        'cookies': {},
        'data': '',
        'headers': {
            'host': 'localhost',
            'content-length': '0',
            'remote-addr': '127.0.0.1',
            'user-agent': 'ASGI-Tools-Test-Client'
        },
    }

    res = await client.patch('/test', data='test')
    json = await res.json()
    assert json['data'] == 'test'

    res = await client.patch('/test', data={'var': '42'})
    json = await res.json()
    assert json['data'] == {'var': '42'}

    res = await client.patch('/test', json={'var': 42})
    json = await res.json()
    assert json['data'] == {'var': 42}

    res = await client.patch('/test?var1=42&var2=34')
    json = await res.json()
    assert json['query'] == {'var1': '42', 'var2': '34'}

    res = await client.patch('/test?var1=42&var2=34', query='var=42')
    json = await res.json()
    assert json['query'] == {'var': '42'}

    res = await client.patch('/test?var1=42&var2=34', query={'var': 42})
    json = await res.json()
    assert json['query'] == {'var': '42'}

    res = await client.patch('/test', cookies={'var': '42'})
    assert res.status_code == 200
    json = await res.json()
    assert json['cookies'] == {'var': '42'}

    from asgi_tools import ResponseRedirect

    # Follow Redirect
    # ---------------
    @app.route('/redirect')
    async def redirect(request):
        raise ResponseRedirect('/')

    res = await client.put('/redirect', follow_redirect=False)
    assert res.status_code == 307
    assert res.headers['location'] == '/'

    # Custom methods
    # --------------
    @app.route('/caldav', methods='PROPFIND')
    async def propfind(request):
        return 'PROPFIND'

    res = await client.propfind('/caldav')
    assert res.status_code == 200
    assert await res.text() == 'PROPFIND'

    # Work with cookies
    # -----------------
    @app.route('/set-cookie')
    async def set_cookie(request):
        res = ResponseRedirect('/test')
        res.cookies['c1'] = 'c1'
        res.cookies['c2'] = 'c2'
        return res

    res = await client.get('/set-cookie')
    assert res.status_code == 200
    assert {n: v.value for n, v in client.cookies.items()} == {'var': '42', 'c1': 'c1', 'c2': 'c2'}

    @app.route('/get-cookie')
    async def get_cookie(request):
        return dict(request.cookies)

    res = await client.get('/get-cookie')
    assert await res.json() == {'var': '42', 'c1': 'c1', 'c2': 'c2'}


async def test_streams(app, client):
    from asgi_tools import ResponseStream
    from asgi_tools._compat import aio_sleep

    async def source(timeout=.001):
        for idx in range(10):
            await aio_sleep(timeout)
            yield idx

    @app.route('/stream')
    async def stream(request):
        return ResponseStream(source(), content_type="plain/text")

    res = await client.get('/stream')
    assert res.status_code == 200

    expected = [str(n).encode() for n in range(10)]
    async for chunk in res.stream():
        assert chunk == expected.pop(0)
