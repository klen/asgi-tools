from asgi_tools import RequestMiddleware, ResponseMiddleware, RouterMiddleware

from .utils.templates import router as template


async def index(request, **params):
    return template.render(request=request, content="Default Page")


router = RouterMiddleware(index, pass_params_only=True)


@router.route('/page1')
async def page1(request, **params):
    return template.render(request=request, content="Page 1")


@router.route('/page2')
async def page1(request, **params):
    return template.render(request=request, content="Page 2")


app = RequestMiddleware(ResponseMiddleware(router))
