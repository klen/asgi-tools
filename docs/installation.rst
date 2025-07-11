Installation
============

Supported Python Versions
-------------------------

ASGI-Tools requires **Python 3.9 or newer**. We recommend using the latest stable release for best performance and compatibility.

.. note::
   **PyPy3** is also supported and can provide performance benefits for some workloads.

Core Dependencies
-----------------

ASGI-Tools automatically installs its minimal dependencies:

* `Http-Router`_ – Fast and flexible HTTP routing
* `Yarl`_ – URL parsing and manipulation
* `Multidict`_ – Multi-value dictionary structures

.. _Http-Router: https://github.com/klen/http-router
.. _Yarl: https://github.com/aio-libs/yarl
.. _Multidict: https://github.com/aio-libs/multidict

Installation Methods
--------------------

Using pip
~~~~~~~~~

Install the latest release from PyPI:

.. code-block:: sh

    pip install asgi-tools

For the latest development version directly from GitHub:

.. code-block:: sh

    pip install git+https://github.com/klen/asgi-tools.git

Using Poetry
~~~~~~~~~~~~

If you manage dependencies with Poetry:

.. code-block:: sh

    poetry add asgi-tools

ASGI Server Requirement
------------------------

ASGI-Tools is a **toolkit/framework** and requires an ASGI server to run your application. We recommend one of the following:

* `Uvicorn`_ – Lightning-fast ASGI server
* `Daphne`_ – HTTP, HTTP2, and WebSocket server
* `Hypercorn`_ – ASGI server with HTTP/2 support

Install your preferred server:

.. code-block:: sh

    pip install uvicorn  # or daphne, or hypercorn

.. _Uvicorn: https://github.com/encode/uvicorn
.. _Daphne: https://github.com/django/daphne
.. _Hypercorn: https://gitlab.com/pgjones/hypercorn/

Verify Installation
--------------------

To verify that ASGI-Tools is installed correctly, create a simple test application:

.. code-block:: python

    from asgi_tools import App

    app = App()

    @app.route("/")
    async def hello(request):
        return "Hello, ASGI-Tools!"

Save this as `test_app.py` and run it with your chosen ASGI server:

.. code-block:: sh

    uvicorn test_app:app

Visit http://127.0.0.1:8000/ in your browser. You should see: `Hello, ASGI-Tools!`

Next Steps
----------

✅ **Continue learning:**

* Read the :doc:`usage` guide for detailed usage examples
* Explore the :doc:`api` reference for all available components
* Check out the `examples <https://github.com/klen/asgi-tools/tree/master/examples>`_ for real-world patterns and best practices

.. _ASGI: https://asgi.readthedocs.io/en/latest/
