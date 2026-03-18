from __future__ import annotations

from asgi_tools import types


def test_types_available():

    assert types.TASGIMessage
    assert types.TASGIScope
    assert types.TASGISend
    assert types.TASGIReceive
    assert types.TASGIApp
    assert types.TJSON
    assert types.TV
    assert types.TVCallable
    assert types.TVAsyncCallable
    assert types.TExceptionHandler
    assert types.TVExceptionHandler
