from __future__ import annotations


def test_parse_options_header():
    from asgi_tools.utils import parse_options_header

    ct, opts = parse_options_header('text/plain; charset="utf-8"')
    assert ct == "text/plain"
    assert opts == {"charset": "utf-8"}

    ct, opts = parse_options_header(
        'form-data; name="test_client.py"; filename="test_client.py"',
    )
    assert ct == "form-data"
    assert opts == {"name": "test_client.py", "filename": "test_client.py"}


async def test_awaitable():
    from asgi_tools.utils import is_awaitable, to_awaitable

    def test1():
        return 1

    async def test2():
        return 2

    async def test3():
        yield 3

    assert not is_awaitable(test1)
    assert is_awaitable(test2)
    assert is_awaitable(test3)

    assert await to_awaitable(test1)() == 1
