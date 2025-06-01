Usage
=====

ASGI Application
-----------------

ASGI-Tools is designed to be used as an ASGI_ Toolkit. You can use any of its
components independently. Despite this ASGI-Tools contains
:py:class:`asgi_tools.App` helper to quickly build ASGI applications.

.. note::
   If you are looking more for a toolkit for your ASGI_ apps go straight to the
   :doc:`api` docs.

.. code-block:: python

    from asgi_tools import App

    app = App()

    @app.route("/")
    async def hello_world(request):
        return "<p>Hello, World!</p>"

Save it as :file:`hello.py` or something similar.

**ASGI-Tools** belongs to the category of ASGI_ web frameworks, so it requires
an ASGI HTTP server to run, such as uvicorn_, daphne_, or hypercorn_.

To run the application, run the command:

.. code-block:: python

   uvicorn hello:app

This launches a very simple builtin server, which is good enough for
testing but probably not what you want to use in production.

Now head over to http://127.0.0.1:8000/, and you should see your hello
world greeting.

The Request Object
------------------

Every callback should accept a request object.  The request object is
documented in the API section and we will not cover it here in detail (see
:class:`~asgi_tools.Request`). Here is a broad overview of some of the most
common operations.

The current request method is available by using the
:attr:`~asgi_tools.Request.method` attribute.  To access form data (data
transmitted in a ``POST`` or ``PUT`` request) you can use the
:attr:`~asgi_tools.Request.form` attribute.  Here is a full example of the two
attributes mentioned above:

.. code-block:: python

   @app.route('/login', methods=['POST', 'PUT'])
    async def login(request):
        error = None
        if request.method == 'POST':
            formdata = await request.form()
            if valid_login(formdata['username'], formdata['password']):
                return log_the_user_in(formdata['username'])

            error = 'Invalid username/password'

        return render_template('login.html', error=error)

To access parameters submitted in the URL (``?key=value``) you can use the
:attr:`~asgi_tools.Request.query` attribute:

.. code-block:: python

    search = request.query.get('search', '')

We recommend accessing URL parameters with `get` or by catching the
:exc:`KeyError` because users might change the URL and presenting them a 400
bad request page in that case is not user friendly.

For a full list of methods and attributes of the request object, head over
to the :class:`~asgi_tools.Request` documentation.

Cookies
```````

Cookies are exposed as a regular dictionary interface through :attr:`~asgi_tools.Request.cookies`:

.. code-block:: python

    session = request.cookies.get('session', '')

File Uploads
````````````

Request files are normally sent as multipart form data (`multipart/form-data`).
The uploaded files are available in :meth:`~asgi_tools.Request.form`:

.. code-block:: python

    formdata = await request.form()

Routing
-------

Modern web applications use meaningful URLs to help users. Users are more
likely to like a page and come back if the page uses a meaningful URL they can
remember and use to directly visit a page.

Use the :meth:`~asgi_tools.App.route` decorator to bind a function to a URL.

.. code-block:: python

    @app.route('/')
    def index():
        return 'Index Page'

    @app.route('/hello', '/hello/world')
    async def hello():
        return 'Hello, World'

    @app.route('/only-post', methods=['POST'])
    async def only_post():
        return request.method

You can do more! You can make parts of the URL dynamic. The every routed
callback should be callable and accepts a :class:`~asgi_tools.Request`.

See also: :py:class:`~asgi_tools.HTTPView`.

Dynamic URLs
------------

All the URLs support regexp. You can use any regular expression to customize your URLs:

.. code-block:: python

   import re

    @app.route(re.compile(r'/reg/(a|b|c)/?'))
    async def regexp(request):
        return request.path

Variable Rules
``````````````

You can add variable sections to a URL by marking sections with
``{variable_name}``. Your function then receives the ``{variable_name}`` from
``request.path_params``.

.. code-block:: python

    @app.route('/user/{username}')
    async def show_user_profile(request):
        username = request.path_params['username']
        return f'User {username}'

By default this will capture characters up to the end of the path or the next /.

Optionally, you can use a converter to specify the type of the argument like
``{variable_name:converter}``.

Converter types:

========= ====================================
``str``   (default) accepts any text without a slash
``int``   accepts positive integers
``float`` accepts positive floating point values
``path``  like string but also accepts slashes
``uuid``  accepts UUID strings
========= ====================================

Convertors are used by prefixing them with a colon, like so:

.. code-block:: python

    @app.route('/post/{post_id:int}')
    async def show_post(request):
        post_id = request.path_params['post_id']
        return f'Post # {post_id}'

Any unknown convertor will be parsed as a regex:

.. code:: python

    @app.route('/orders/{order_id:\d{3}}')
    async def orders(request):
        order_id = request.path_params['order_id']
        return f'Order # {order_id}'


Static Files
------------

Set static url prefix and directories when initializing your app:

.. code-block:: python

    from asgi_tools import App

    app = App(static_url_prefix='/assets', static_folders=['static'])

And your static files will be available at url ``/static/{file}``.


Redirects and Errors
--------------------

To redirect a user to another endpoint, use the :class:`~.asgi_tools.ResponseRedirect`
class; to abort a request early with an error code, use the
:func:`~asgi_tools.ResponseError` class:

.. code-block:: python

    from asgi_tools import ResponseRedirect, ResponseError

    @app.route('/')
    async def index(request):
        return ResponseRedirect('/login')

    @app.route('/login')
    async def login(request):
        raise ResponseError(status_code=401)
        this_is_never_executed()

This is a rather pointless example because a user will be redirected from
the index to a page they cannot access (401 means access denied) but it
shows how that works.

By default only description is shown for each error code.  If you want to
customize the error page, you can use the :meth:`~asgi_tools.App.on_error`
decorator:

.. code-block:: python

    @app.on_error(ResponseError)
    async def process_http_errors(request, error):
      if error.status_code == 404:
        return render_template('page_not_found.html'), 404
      return error

It's possible to bind the handlers not only for status codes, but for the
exceptions themself:

.. code-block:: python

    @app.on_error(TimeoutError)
    async def timeout(request, error):
        return 'Something bad happens'

.. _about-responses:

About Responses
---------------

The return value from a view function is automatically converted into a
response object for you. If the return value is a string it's converted into a
response object with the string as response body, a ``200 OK`` status code and
a :mimetype:`text/html` mimetype. If the return value is a dict or list,
:func:`json.dumps` is called to produce a response.  The logic that ASGI-Tools
applies to converting return values into response objects is as follows:

1.  If a result is response :class:`~asgi_tools.Response` it's directly
    returned from the view.
2.  If it's a string, a response :class:`~asgi_tools.ResponseHTML` is created with
    that data and the default parameters.
3.  If it's a dict/list/bool/None, a response :class:`~asgi_tools.ResponseJSON`
    is created
4.  If a tuple is returned the items in the tuple can provide extra
    information. Such tuples have to be in the form ``(status, response
    content)``, ``(status, response content, headers)``.  The
    ``status``:``int`` value will override the status code and
    ``headers``:``dict[str, str]`` a list or dictionary of additional header
    values.
5.  If none of that works, ASGI-Tools will convert the return value to a string
    and return as html.


.. code-block:: python

    @app.route('/html')
    async def html(request):
        return '<b>HTML is here</b>'

    @app.route('/json')
    async def json(request):
        return {'json': 'here'}

    @app.route('/text')
    async def text(request):
        res = ResponseText('response is here')
        res.headers['x-custom'] = 'value'
        res.cookies['x-custom'] = 'value'
        return res

    @app.route('/short-form')
    async def short_form(request):
        return 418, 'Im a teapot'


.. _middlewares:

Middlewares
-----------

:py:class:`asgi_tools.App` supports middlewares, which provide a flexible way
to define a chain of functions that handles every web requests.

1. As an ASGI_ application `asgi_tools.App` can be proxied with any ASGI_ middlewares:

   .. code-block:: python

        from asgi_tools import App
        from sentry_asgi import SentryMiddleware

        app = App()
        app = SentryMiddleware(app)

2. Alternatively you can decorate any ASGI_ middleware to connect it to an app:

   .. code-block:: python

        from asgi_tools import App
        from sentry_asgi import SentryMiddleware

        app = App()
        app.middleware(SentryMiddleware)

3. Internal middlewares. For middlewares it's possible to use simpler interface
   which one accepts a request and can return responses.

   .. code-block:: python

        from asgi_tools import App


        app = App()

        @app.middleware
        async def simple_md(app, request, receive, send):
            try:
                response = await app(request, receive, send)
                response.headers['x-simple-md'] = 'passed'
                return response
            except RuntimeError:
                return ResponseHTML('Middleware Exception')

Nested applications
-------------------

Sub applications are designed for solving the problem of the big monolithic
code base.

.. code-block:: python

    from asgi_tools import App

    # Main application
    app = App()

    @app.route('/')
    def index(request):
        return 'OK'

    # Sub application
    subapp = App()

    @subapp.route('/route')
    def subpage(request):
        return 'OK from subapp'

    # Connect the subapplication with an URL prefix
    app.route('/sub')(subapp)

    # await client.get('/sub/route').text() == 'OK from subapp'

Middlewares from app and subapp are chained (only internal middlewares are
supported for nested apps).


.. Links

.. _ASGI: https://asgi.readthedocs.io/en/latest/
.. _uvicorn: http://www.uvicorn.org/
.. _daphne: https://github.com/django/daphne/
.. _hypercorn: https://pgjones.gitlab.io/hypercorn/
