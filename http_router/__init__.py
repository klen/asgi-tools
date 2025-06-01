from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Pattern, Union

__all__ = [
    "Router",
    "RouterError",
    "NotFoundError",
    "InvalidMethodError",
    "PrefixedRoute",
]


class RouterError(Exception):
    pass


class NotFoundError(RouterError):
    pass


class InvalidMethodError(RouterError):
    pass


@dataclass
class Match:
    target: Callable
    params: Mapping[str, str]


class Route:
    def __init__(self, pattern: Pattern[str], methods: Iterable[str], target: Callable):
        self.pattern = pattern
        self.methods = {m.upper() for m in methods}
        self.target = target

    def match(self, path: str, method: str) -> Match | None:
        m = self.pattern.match(path)
        if not m:
            return None
        if method.upper() not in self.methods:
            raise InvalidMethodError(method)
        return Match(self.target, m.groupdict())


class Router:
    RouterError = RouterError
    NotFoundError = NotFoundError
    InvalidMethodError = InvalidMethodError

    def __init__(self, *, trim_last_slash: bool = False, validator: Callable | None = None, converter: Callable | None = None):
        self.trim_last_slash = trim_last_slash
        self.validator = validator
        self.converter = converter
        self.routes: list[Route] = []

    def _compile(self, path: Union[str, Pattern[str]]) -> Pattern[str]:
        if isinstance(path, re.Pattern):
            return path
        # convert {name} or {name:expr}
        pattern = ""
        last = 0
        for match in re.finditer(r"{([^{}]+)}", path):
            pattern += re.escape(path[last:match.start()])
            name = match.group(1)
            if ":" in name:
                name, conv = name.split(":", 1)
                if conv == "int":
                    part = fr"(?P<{name}>\\d+)"
                else:
                    part = fr"(?P<{name}>{conv})"
            else:
                part = fr"(?P<{name}>[^/]+)"
            pattern += part
            last = match.end()
        pattern += re.escape(path[last:])
        if self.trim_last_slash:
            pattern = pattern.rstrip("/")
            pattern += "/?"
        return re.compile("^" + pattern + "$")

    def route(self, *paths: Union[str, Pattern[str]], methods: Iterable[str] | None = None):
        methods_set = set(m.upper() for m in (methods or ["GET"]))

        def decorator(target: Callable):
            if self.validator and not self.validator(target):
                raise RouterError("Invalid target")
            for path in paths:
                self.routes.append(Route(self._compile(path), methods_set, target))
            return target

        return decorator

    def bind(self, target: Callable, *paths: Union[str, Pattern[str]], methods: Iterable[str] | None = None, **_: object):
        return self.route(*paths, methods=methods)(target)

    def __call__(self, path: str, method: str = "GET") -> Match:
        if self.trim_last_slash and path != "/":
            path = path.rstrip("/")
        errors = []
        for route in self.routes:
            try:
                match = route.match(path, method)
            except InvalidMethodError:
                errors.append("method")
                continue
            if match:
                params = match.params
                if self.converter:
                    params = {k: self.converter(v) for k, v in params.items()}
                return Match(match.target, params)
        if errors:
            raise InvalidMethodError(method)
        raise NotFoundError(path)


class PrefixedRoute:
    def __init__(self, path: str, methods: Iterable[str], target: Callable):
        self.path = path.rstrip("/")
        self.methods = {m.upper() for m in methods}
        self.target = target
