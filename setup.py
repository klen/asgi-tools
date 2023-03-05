"""Setup the library."""
from __future__ import annotations

import os
import sys

from setuptools import setup

try:
    from Cython.Build import cythonize
except ImportError:
    cythonize = None


NO_EXTENSIONS = (
    sys.implementation.name != "cpython"
    or bool(os.environ.get("ASGI_TOOLS_NO_EXTENSIONS"))
    or cythonize is None
)

print("*********************")
print("* Pure Python build *" if NO_EXTENSIONS else "* Accelerated build *")
print("*********************")

setup(
    setup_requires=["wheel"],
    ext_modules=(
        []
        if NO_EXTENSIONS or cythonize is None
        else cythonize("asgi_tools/*.pyx", language_level=3)
    ),
)

# ruff: noqa: T201
