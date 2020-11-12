ASGI-Tools
##########

.. _description:

**asgi-tools** -- Tools to make ASGI Applications

**Features:**

- `Request`             -- Parse ASGI scope, get url, headers, cookies, read a request's data/json/form-data
- `Response`            -- Send HTTP (html, json) responses
- `RequestMiddleware`   -- Parse a scope and insert the parsed request into the scope
- `ResponseMiddleware`  -- Parse responses and convert them into ASGI messages
- `RouterMiddleware`    -- Route HTTP requests
- `LifespanMiddleware`  -- Process a lifespan cycle
- `AppMiddleware`       -- A combined (request, response, router, lifespan) middleware to quikly create ASGI apps

.. _badges:

.. image:: https://github.com/klen/asgi-tools/workflows/tests/badge.svg
    :target: https://github.com/klen/asgi-tools/actions
    :alt: Tests Status

.. image:: https://img.shields.io/pypi/v/asgi-tools
    :target: https://pypi.org/project/asgi-tools/
    :alt: PYPI Version

.. _contents:

.. contents::

.. _requirements:

Requirements
=============

- python >= 3.7

.. _installation:

Installation
=============

**asgi-tools** should be installed using pip: ::

    pip install asgi-tools


Usage
=====

**TODO**

.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/klen/asgi-tools/issues

.. _contributing:

Contributing
============

Development of the project happens at: https://github.com/klen/asgi-tools

.. _license:

License
========

Licensed under a `MIT license`_.


.. _links:

.. _klen: https://github.com/klen
.. _MIT license: http://opensource.org/licenses/MIT

