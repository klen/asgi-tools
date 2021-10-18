"""Setup the package."""


# Parse requirements
# ------------------
import pkg_resources
import pathlib


def parse_requirements(path: str) -> 'list[str]':
    with pathlib.Path(path).open() as requirements:
        return [str(req) for req in pkg_resources.parse_requirements(requirements)]


# Setup extensions
# ----------------
import os
import sys
from setuptools import Extension

NO_EXTENSIONS = (
    sys.implementation.name != 'cpython' or
    bool(os.environ.get("ASGI_TOOLS_NO_EXTENSIONS"))
)
EXT_MODULES = [] if NO_EXTENSIONS else [
    Extension("asgi_tools.multipart", ["asgi_tools/multipart.c"], extra_compile_args=['-O2']),
    Extension("asgi_tools.forms", ["asgi_tools/forms.c"], extra_compile_args=['-O2']),
]


# Setup package
# -------------
from setuptools import setup

setup(
    setup_requires=["wheel"],

    ext_modules=EXT_MODULES,

    install_requires=parse_requirements('requirements/requirements.txt'),
    extras_require={
        'tests': parse_requirements('requirements/requirements-tests.txt'),
        'build': parse_requirements('requirements/requirements-build.txt'),
        'docs': parse_requirements('requirements/requirements-docs.txt'),
        'examples': parse_requirements('requirements/requirements-examples.txt'),
        'orjson': parse_requirements('requirements/requirements-orjson.txt'),
        'ujson': parse_requirements('requirements/requirements-ujson.txt'),
    },
)

# pylama:ignore=E402,D
