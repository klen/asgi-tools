"""A simple example for ASGI-Tools.

The example requires httpx to be installed.
"""

from httpx import AsyncClient

from asgi_tools import App


app = App()
client = AsyncClient(timeout=10.0)


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

    status, data = 200, response.json()
    if data.get('error'):
        status = 404
        content = f"""
            <h1>{currency} not found</h1>
            <a href="/">Go home</a>
        """
    else:
        data['rates'].setdefault(currency, 1.0)
        table = ""
        for cur, rate in sorted(data['rates'].items()):
            table += f"""
                <tr class="{data['base'] == cur and 'bg-primary'}"
                    onclick="window.location='/base/{cur}'" role="button">
                    <td>
                        <a href="/base/{cur}" class="{ data['base'] == cur and 'text-light'}">{cur}</a>
                    </td>
                    <td>{ round(rate, 3) } { data['base'] }</td>
                </tr>
            """
        content = f"""
            <h1>Currency rates: { data['base'] }
                <span class="badge badge-secondary">{data['date']}</span></h1>
            <table class="table table-hover table-dark">
                <tr> <th>Currency</th> <th>Rate</th> </tr>
                {table}
            </table>
        """
    return status, f"""
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap.min.css">
    <div class="container p-3">{ content }</div>
"""
