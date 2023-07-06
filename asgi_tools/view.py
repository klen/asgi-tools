from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, Optional

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from http_router.types import TMethods

    from .request import Request
    from .router import Router

HTTP_METHODS: Final = {
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "DELETE",
    "CONNECT",
    "OPTIONS",
    "TRACE",
    "PATCH",
}


class HTTPView:
    """Class-based view pattern for handling HTTP method dispatching.

    .. code-block:: python

        @app.route('/custom')
        class CustomEndpoint(HTTPView):

            async def get(self, request):
                return 'Hello from GET'

            async def post(self, request):
                return 'Hello from POST'

        # ...
        async def test_my_endpoint(client):
            response = await client.get('/custom')
            assert await response.text() == 'Hello from GET'

            response = await client.post('/custom')
            assert await response.text() == 'Hello from POST'

            response = await client.put('/custom')
            assert response.status_code == 405

    """

    def __new__(cls, request: Request, **opts):
        """Init the class and call it."""
        self = super().__new__(cls)
        return self(request, **opts)

    @classmethod
    def __route__(cls, router: Router, *paths: str, methods: Optional[TMethods] = None, **params):
        """Bind the class view to the given router."""
        view_methods = dict(inspect.getmembers(cls, inspect.isfunction))
        methods = methods or [m for m in HTTP_METHODS if m.lower() in view_methods]
        return router.bind(cls, *paths, methods=methods, **params)

    def __call__(self, request: Request, **opts) -> Awaitable:
        """Dispatch the given request by HTTP method."""
        method = getattr(self, request.method.lower())
        return method(request, **opts)
