from httpx import AsyncClient
from jinja2 import Template

from asgi_tools import AppMiddleware


client = AsyncClient(timeout=10.0)
template = Template(
    """
    <style>
        body {font-family: Helvetica}
        table {border-collapse: collapse}
        th, td { padding: .4rem 1rem; border: 1px solid #ccc }
    </style>
    {% if data %}
        <h1>{{ data.base }} rates {{ data.date }}</h1>
        <table>
            <tr> <th>Currency</th> <th>Rate</th> </tr>
            {% for cur, rate in data.rates.items()|sort %}
            <tr>
                <td>
                    {% if data.base == cur %}
                        <b>{{ cur }}</b>
                    {% else %}
                        <a href="/base/{{ cur }}">{{ cur }}</a>
                    {% endif %}
                </td>
                <td>{{ rate|round(3) }}</td>
            </tr>
            {% endfor %}
        </table>
    {% else %}
        <h1>{{ currency }} not found</h1>
        <a href="/">Go home</a>
    {% endif %}
    """
)


async def pageDefault(request):
    return 404, 'Page not found'


app = AppMiddleware(app=pageDefault)


@app.on_startup
async def startup():
    print('Start application: %r' % app)


@app.on_shutdown
async def shutdown():
    print('Finish application %r' % app)
    await client.aclose()


@app.route('/', '/base/{currency}')
async def rates(request, currency='USD', **kwargs):
    response = await client.request(
        'GET', f"https://api.exchangeratesapi.io/latest?base={ currency }")
    data = response.json()
    if data.get('error'):
        return 404, template.render(currency=currency, data=None)

    data['rates'].setdefault(currency, 1.0)
    return template.render(data=data)
