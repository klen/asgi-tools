from httpx import AsyncClient


async def test_app():
    from asgi_lifespan import LifespanManager
    from asgi_tools import App

    app = App()

    @app.route('/testurl')
    async def test_request(request, **kwargs):
        data = await request.json()
        first_name = data.get('first_name', 'Anonymous')
        last_name = request.query.get('last_name', 'Test')
        return f"Hello {first_name} {last_name} from '{ request.url.path }'"

    async with LifespanManager(app):
        async with AsyncClient(app=app, base_url='http://testserver') as client:
            res = await client.get('/')
            assert res.status_code == 404

            res = await client.post(
                '/testurl?last_name=Daniels',
                json={'first_name': 'Jack'},
                headers={'test-header': 'test-value'},
                cookies={'session': 'test-session'})
            assert res.status_code == 200
            assert res.text == "Hello Jack Daniels from '/testurl'"
            assert res.headers['content-length'] == str(len(res.text))
