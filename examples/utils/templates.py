from jinja2 import Template


request_info = Template(
    """
        <html>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
            <body>
                <div class="container">
                    <h1 class="mb-4"> ASGI Tools Request/Response example </h1>

                    <h3>{{ url }}</h3>
                    <h3>Charset: {{ charset }}</h3>

                    <h3>Headers</h3>
                    <table class="table table-hover">
                        <thead><tr><th>Name</th><th>Value</th></thead>
                        {% for header, value in headers.items() %}
                            <tr>
                                <td>{{ header }}</td>
                                <td>{{ value }}</td>
                            </tr>
                        {% endfor %}
                    </table>

                    <h3>Query</h3>
                    <table class="table table-hover">
                        <thead><tr><th>Name</th><th>Value</th></thead>
                        {% for name in query %}
                            <tr>
                                <td>{{ name }}</td>
                                <td>{{ query.get(name) }}</td>
                            </tr>
                        {% endfor %}
                    </table>

                    <h3>Cookies</h3>
                    <table class="table table-hover">
                        <thead><tr><th>Name</th><th>Value</th></thead>
                        {% for name, value in cookies.items() %}
                            <tr>
                                <td>{{ name }}</td>
                                <td>{{ value }}</td>
                            </tr>
                        {% endfor %}
                    </table>

                    <h3>Body</h3>
                    <pre> {{ text }} </pre>

                </div>
            </body>
        </html>
    """
)


router = Template(
    """
        <html>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
            <body>
                <div class="container">
                    <nav class="nav nav-tabs">
                        <a class="nav-link {{ request.url.path == '/' and 'active' }}" href="/">Default</a>
                        <a class="nav-link {{ request.url.path == '/page1' and 'active' }}" href="/page1">Page1</a>
                        <a class="nav-link {{ request.url.path == '/page2' and 'active' }}" href="/page2">Page2</a>
                    </nav>
                    <div> {{ content }} </div>
                </div>
            </body>
        </html>
    """
)
