import pytest


@pytest.mark.benchmark(group="req-res", disable_gc=True)
def test_benchmark_req_res(benchmark, GenRequest):
    from asgi_tools import Request, parse_response

    scope = GenRequest(
        '/test', query={'param': 'value'}, headers={'header': 'value'}, cookies={'cookie': 'value'}
    ).scope

    async def send(msg):
        pass

    def run_benchmark():
        request = Request(scope)
        assert request.method
        assert request.query['param']
        assert request.headers['header']
        assert request.cookies['cookie']

        response = parse_response('body')
        coro = response(None, None, send)
        try:
            coro.send(None)
        except StopIteration:
            pass

    benchmark(run_benchmark)


@pytest.mark.benchmark(group="formdata", disable_gc=True)
def test_benchmark_formdata(benchmark):
    from asgi_tools.forms import FormReader

    def run_benchmark():
        reader = FormReader('utf-8')
        parser = reader.init_parser(None, 0)
        parser.write(b'&value=test%20passed')
        parser.finalize()
        return reader.form

    form = benchmark(run_benchmark)
    assert dict(form) == {'value': 'test passed'}


@pytest.mark.benchmark(group="app", disable_gc=True)
def test_benchmark_app(benchmark, app, client):

    @app.route('/path')
    async def page(request):
        return 'OK'

    @app.middleware
    async def md(app, request, receive, send):
        response = await app(request, receive, send)
        response.headers['x-app'] = 'OK'
        return response

    scope = client.build_scope('/path', type='http')

    messages = []

    async def send(msg):
        messages.append(msg)

    def run_benchmark():
        coro = app(scope, None, send)
        try:
            coro.send(None)
        except StopIteration:
            pass

        nonlocal messages
        res = list(messages)
        messages = []
        return res

    res = benchmark(run_benchmark)
    assert res == [
        {
            'status': 200,
            'type': 'http.response.start',
            'headers': [
                (b'content-type', b'text/html; charset=utf-8'),
                (b'x-app', b'OK'),
                (b'content-length', b'2'),
            ],
        },
        {
            'type': 'http.response.body',
            'body': b'OK',
        }

    ]
