"""A simple example for ASGI-Tools."""

from httpx import AsyncClient
from jinja2 import Template

from asgi_tools import AppMiddleware


client = AsyncClient(timeout=10.0)
template = Template(
    """
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css">
    <div class="container p-3">
        {% if data %}
            <h1>Currency rates: {{ data.base }}
                <span class="badge badge-secondary">{{ data.date }}</span></h1>
            <table class="table table-hover table-dark">
                <tr> <th>Currency</th> <th>Rate</th> </tr>
                {% for cur, rate in data.rates.items()|sort %}
                <tr class="{{ data.base == cur and 'bg-primary' }}"
                    onclick="window.location='/base/{{cur}}'" role="button">
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
    </div>
    """
)


app = AppMiddleware()


@app.on_startup
async def startup():
    """Just a presentation of a start event."""
    print('Start application: %r' % app)


@app.on_shutdown
async def shutdown():
    """Just a finish event. Actually do some work here."""
    print('Finish application %r' % app)
    await client.aclose()


@app.route('/', '/base/{currency}')
async def rates(request, currency='USD', **kwargs):
    """Load currency rates and render a template."""
    response = await client.request(
        'GET', f"https://api.exchangeratesapi.io/latest?base={ currency }")
    data = response.json()
    if data.get('error'):
        return 404, template.render(currency=currency, data=None)

    data['rates'].setdefault(currency, 1.0)
    return template.render(data=data)
