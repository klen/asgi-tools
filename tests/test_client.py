"""Simple Test Client."""


async def test_client(app):
    from asgi_tools.tests import ASGITestClient

    client = ASGITestClient(app)

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

    res = await client.get('/')
    assert res
    assert res.status_code == 200
    assert res.headers
    assert res.headers['content-type']
    assert res.headers['content-length'] == '2'
    assert res.text == 'OK'

    res = await client.patch('/test')
    assert res.status_code == 200
    assert res.json() == {
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
    assert res.json()['data'] == 'test'

    res = await client.patch('/test', data={'var': '42'})
    assert res.json()['data'] == {'var': '42'}

    res = await client.patch('/test', json={'var': 42})
    assert res.json()['data'] == {'var': 42}

    res = await client.patch('/test?var1=42&var2=34')
    assert res.json()['query'] == {'var1': '42', 'var2': '34'}

    res = await client.patch('/test?var1=42&var2=34', query='var=42')
    assert res.json()['query'] == {'var': '42'}

    res = await client.patch('/test?var1=42&var2=34', query={'var': 42})
    assert res.json()['query'] == {'var': '42'}

    res = await client.patch('/test', cookies={'var': '42'})
    assert res.status_code == 200
    assert res.json()['cookies'] == {'var': '42'}

    from asgi_tools import ResponseRedirect

    # Follow Redirect
    # ---------------
    @app.route('/redirect')
    async def redirect(request):
        return ResponseRedirect('/')

    res = await client.put('/redirect')
    assert res.status_code == 200

    # Custom methods
    # --------------
    @app.route('/caldav', methods='PROPFIND')
    async def propfind(request):
        return 'PROPFIND'

    res = await client.propfind('/caldav')
    assert res.status_code == 200
    assert res.text == 'PROPFIND'

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
    assert res.json() == {'var': '42', 'c1': 'c1', 'c2': 'c2'}
