from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

__all__ = ["URL"]

class URL(str):
    def __new__(cls, url: str):
        obj = str.__new__(cls, url)
        parsed = urlparse(url)
        obj.scheme = parsed.scheme
        obj.host = parsed.netloc
        obj.port = parsed.port or (80 if parsed.scheme == "http" else 443 if parsed.scheme else None)
        obj.path = parsed.path
        obj.raw_path = parsed.path
        obj.query_string = parsed.query
        obj.raw_query_string = parsed.query
        obj._query = None
        return obj

    @classmethod
    def build(cls, *, host: str, scheme: str = "http", path: str = "", query_string: str = "", encoded: bool = False):
        url = f"{scheme}://{host}{path}"
        if query_string:
            url += f"?{query_string}"
        return cls(url)

    def with_query(self, query: dict | str):
        if isinstance(query, dict):
            from urllib.parse import urlencode
            query = urlencode(query, doseq=True)
        base = self.split("?", 1)[0]
        return URL(f"{base}?{query}")

    @property
    def query(self):
        if self._query is None:
            self._query = dict(parse_qsl(self.query_string))
        return self._query

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"URL('{str(self)}')"
