import pytest


def run_benchmark(scope):
    from asgi_tools import Request, parse_response

    request = Request(scope)
    assert request.method
    assert request.url.query['param']
    assert request.headers['header']
    assert request.cookies['cookie']

    response = parse_response('body')
    msg = response.msg_start()
    assert msg
    return msg


@pytest.mark.parametrize('aiolib', ['asyncio'])
def test_benchmark(aiolib, benchmark, client):
    scope = client.build_scope(
        '/test', query={'param': 'value'}, headers={'header': 'value'},
        cookies={'cookie': 'value'}, type='http', method='GET')

    msg = benchmark(run_benchmark, scope)
    assert msg == {
        'type': 'http.response.start', 'status': 200,
        'headers': [(b'content-type', b'text/html; charset=utf-8')]
    }
