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
