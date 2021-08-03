"""A simple example for ASGI-Tools.

The example requires httpx to be installed.
"""

import datetime

from httpx import AsyncClient

from asgi_tools import App


app = App()
del app.exception_handlers[Exception]
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
async def rates(request):
    """Load currency rates and render a template."""
    currency = request.path_params.get('currency', 'USD')
    response = await client.request(
        'GET', f"http://www.floatrates.com/daily/{currency.lower()}.json")

    if response.status_code != 200:
        status = 404
        content = f"""
            <h1>{currency} not found</h1>
            <a href="/">Go home</a>
        """

    else:
        status, data = 200, response.json()
        table = ""
        date = datetime.datetime.utcnow().isoformat()
        data[currency.lower()] = {'code': currency, 'rate': 1.0}
        for _, info in sorted(data.items()):
            code, rate = info['code'], info['rate']
            table += f"""
                <tr class="{code == currency and 'bg-primary'}"
                    onclick="window.location='/base/{code}'" role="button">
                    <td>
                        <a href="/base/{code}" class="{ code == currency and 'text-light'}">{code}</a>
                    </td>
                    <td>{ round(rate, 3) } { currency }</td>
                </tr>
            """
        content = f"""
            <h1>Currency rates: { currency }
                <span class="badge badge-secondary">{date}</span></h1>
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
