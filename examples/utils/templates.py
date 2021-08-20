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

websockets = Template(
    """
        <html>
            <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
            <body>
                <div class="container">
                    <h1 class="mb-4"> ASGI Tools Websockets example </h1>
                    <div class="mb-4 p-2" style="background: #ccc; height: 30em; overflow-y: scroll;" id="messages">
                    </div>
                    <button class="btn btn-primary" onclick="send('ping')">Send Ping</button>
                    <button class="btn btn-success" onclick="connect()">Connect</button>
                    <button class="btn btn-danger" onclick="disconnect()">Disconnect</button>
                </div>
            </body>
            <script>
                let ws, messages = document.querySelector('#messages');

                window.onmessage = (text, className) => {
                    let message = document.createElement('p');
                    message.className = className;
                    message.innerHTML = text;
                    messages.appendChild(message);
                    messages.scrollTop = messages.scrollHeight;
                }

                window.send = (message) => {
                    ws.send(message);
                    onmessage(`Client (${Date.now()}): ${message}`, 'text-success');
                }

                window.disconnect = () => { ws.close() }

                window.connect = () => {
                    if (ws && ws.readyState == 1) return;

                    ws = new WebSocket(`ws://${location.host}/socket`);

                    ws.onopen = (e) => {
                        onmessage('Connected to server', 'text-danger');
                    }

                    ws.onclose = (e) => {
                        onmessage('Disconnected from server', 'text-danger');
                    }

                    ws.onmessage = (e) => {
                        onmessage(`Server (${Date.now()}): ${e.data}`, 'text-primary');
                    }
                }

                connect();

            </script>
        </html>
    """
)

static = Template(
    """
    <html>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-EVSTQN3/azprG1Anm3QDgpJLIm9Nao0Yz1ztcQTwFspd3yD65VohhpuuCOmLASjC" crossorigin="anonymous">
        <body>
            <div class="container">
                <h1 class="mb-4"> ASGI Tools Static files example </h1>
                <div class="mp-3">
                    <img class="img-fluid" src="/image?{{salt}}" />
                </div>
                <form method="POST" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label for="upload" class="form-label"> Select an image </label>
                        <input class="form-control" type="file" id="upload" name="upload" />
                    </div>
                    <button type="submit" class="btn btn-primary">Submit</button>
                </form>
            </div>
        </body>
    </html>
    """
)
