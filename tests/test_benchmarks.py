import pytest


@pytest.mark.benchmark(group="req-res", disable_gc=True)
def test_benchmark_req_res(benchmark, GenRequest):
    from asgi_tools import Request, parse_response

    scope = dict(GenRequest(
        '/test', query={'param': 'value'}, headers={'header': 'value'}, cookies={'cookie': 'value'}
    ))

    def run_benchmark():
        request = Request(scope)
        assert request.method
        assert request.url.query['param']
        assert request.headers['header']
        assert request.cookies['cookie']

        response = parse_response('body')
        return response.msg_start()

    msg = benchmark(run_benchmark)
    assert msg == {
        'type': 'http.response.start', 'status': 200,
        'headers': [(b'content-type', b'text/html; charset=utf-8')]
    }


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
