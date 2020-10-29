import re
from os import path as op

from setuptools import setup


def _read(fname):
    try:
        return open(op.join(op.dirname(__file__), fname)).read()
    except IOError:
        return ''


meta = _read('asgi_tools/__init__.py')
install_requires = [
    line.replace('==', '>=') for line in _read('requirements.txt').split('\n')
    if line and not line.startswith(('#', '-'))]

setup(
    name='asgi-tools',
    version=re.search(r'^__version__\s*=\s*"(.*)"', meta, re.M).group(1),
    license=re.search(r'^__license__\s*=\s*"(.*)"', meta, re.M).group(1),
    description="Tools to make ASGI Applications",
    long_description=_read('README.rst'),

    packages=['asgi_tools'],

    author='Kirill Klenov',
    author_email='horneds@gmail.com',
    homepage="https://github.com/klen/asgi-tools",
    repository="https://github.com/klen/asgi-tools",
    keywords="asgi tools request response",

    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        "Topic :: Software Development :: Libraries",
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    install_requires=install_requires,
)
