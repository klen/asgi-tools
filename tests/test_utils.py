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

    assert 1 == await to_awaitable(test1)()
