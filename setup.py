"""Setup the package."""

import os
import sys
from setuptools import setup, Extension


NO_EXTENSIONS = (
    sys.implementation.name != 'cpython' or
    bool(os.environ.get("ASGI_TOOLS_NO_EXTENSIONS"))
)
EXT_MODULES = [] if NO_EXTENSIONS else [
    Extension("asgi_tools.multipart", ["asgi_tools/multipart.c"], extra_compile_args=['-O2']),
    Extension("asgi_tools.forms", ["asgi_tools/forms.c"], extra_compile_args=['-O2']),
]


setup(
    setup_requires=["wheel"],
    ext_modules=EXT_MODULES,
)
