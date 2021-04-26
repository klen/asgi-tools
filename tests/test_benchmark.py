import pytest


def test_benchmark_req_res(benchmark, client):
    from asgi_tools import Request, parse_response

    scope = client.build_scope(
        '/test', query={'param': 'value'}, headers={'header': 'value'},
        cookies={'cookie': 'value'}, type='http', method='GET')

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
