# ASGI-Tools

![ASGI-Tools][logo]

**asgi-tools** is a lightweight [ASGI][asgi-spec] toolkit for building ASGI applications faster.

[![Tests Status][tests-badge]][tests-url] [![Documentation Status][docs-badge]][docs-url]
[![PyPI Version][pypi-badge]][pypi-url] [![Python Versions][pyversions-badge]][pypi-url]

Full documentation: <https://klen.github.io/asgi-tools>

ASGI-Tools is a toolkit to quickly build lightweight ASGI applications, middlewares and tools.
For instance, these middlewares were built with it:

- [ASGI-Sessions](https://github.com/klen/asgi-sessions)
- [ASGI-Babel](https://github.com/klen/asgi-babel)
- [ASGI-Prometheus](https://github.com/klen/asgi-prometheus)

## Features

- Supports the most popular async Python libraries: [Asyncio][asyncio],
  [Trio][trio], and [Curio][curio]
- [Request][request]: parse the ASGI scope and get the url, headers, cookies,
  data, json or form data
- [Response][responses]: send HTTP (text, html, json, stream, SSE, file, http
  errors) responses
- [ResponseWebSocket][websocket]: work with websockets
- [RequestMiddleware][requestmw]: parse a scope and insert the parsed request
  into the scope
- [ResponseMiddleware][responsemw]: parse responses and convert them into ASGI
  messages
- [RouterMiddleware][routermw]: route HTTP requests
- [LifespanMiddleware][lifespanmw]: process a lifespan cycle
- [StaticFilesMiddleware][staticmw]: serve static files from URL prefixes
- [ASGITestClient][testclient]: a test client with websockets support to test
  ASGI applications
- [App][app]: a simple foundation for ASGI apps

## Requirements

Python 3.11 or newer.
PyPy3 is also supported.

ASGI-Tools belongs to the category of ASGI web frameworks, so it requires an ASGI HTTP server to run,
such as [uvicorn][uvicorn], [daphne][daphne], or [hypercorn][hypercorn].

## Installation

Install with pip:

```sh
pip install asgi-tools
```

## Quick Example

You can use any ASGI-Tools component independently.
The library also includes an [App][app] helper to quickly build ASGI applications.

Save this to `app.py`:

```python
from asgi_tools import App

app = App()


@app.route("/")
async def hello(request):
    return "Hello World!"
```

Run it with `uvicorn`:

```sh
uvicorn app:app
```

## Bug tracker

If you have any suggestions, bug reports, or annoyances, report them to the [issue tracker][issues].

## Contributing

Development of the project happens at <https://github.com/klen/asgi-tools>.

## License

Licensed under the [MIT license][mit].

[logo]: https://raw.githubusercontent.com/klen/asgi-tools/develop/.github/assets/asgi-tools.png
[tests-badge]: https://github.com/klen/asgi-tools/workflows/tests/badge.svg
[tests-url]: https://github.com/klen/asgi-tools/actions
[docs-badge]: https://github.com/klen/asgi-tools/workflows/docs/badge.svg
[docs-url]: https://klen.github.io/asgi-tools
[pypi-badge]: https://img.shields.io/pypi/v/asgi-tools
[pypi-url]: https://pypi.org/project/asgi-tools/
[pyversions-badge]: https://img.shields.io/pypi/pyversions/asgi-tools
[asgi-spec]: https://asgi.readthedocs.io/en/latest/
[asyncio]: https://docs.python.org/3/library/asyncio.html
[trio]: https://trio.readthedocs.io/en/stable/index.html
[curio]: https://github.com/dabeaz/curio
[request]: https://klen.github.io/asgi-tools/api.html#request
[responses]: https://klen.github.io/asgi-tools/api.html#responses
[websocket]: https://klen.github.io/asgi-tools/api.html#responsewebsocket
[requestmw]: https://klen.github.io/asgi-tools/api.html#requestmiddleware
[responsemw]: https://klen.github.io/asgi-tools/api.html#responsemiddleware
[routermw]: https://klen.github.io/asgi-tools/api.html#routermiddleware
[lifespanmw]: https://klen.github.io/asgi-tools/api.html#lifespanmiddleware
[staticmw]: https://klen.github.io/asgi-tools/api.html#staticfilesmiddleware
[testclient]: https://klen.github.io/asgi-tools/api.html#asgi_tools.tests.ASGITestClient
[app]: https://klen.github.io/asgi-tools/api.html#application
[uvicorn]: http://www.uvicorn.org/
[daphne]: https://github.com/django/daphne/
[hypercorn]: https://github.com/pgjones/hypercorn/
[issues]: https://github.com/klen/asgi-tools/issues
[mit]: http://opensource.org/licenses/MIT
