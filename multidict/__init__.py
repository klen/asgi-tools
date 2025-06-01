from __future__ import annotations

from collections.abc import Iterable

__all__ = ["MultiDict", "CIMultiDict"]

class _Base(dict):
    def getall(self, key: str):
        val = self.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return list(val)
        return [val]

    def add(self, key: str, value):
        if key in self:
            cur = self[key]
            if isinstance(cur, list):
                cur.append(value)
            else:
                super().__setitem__(key, [cur, value])
        else:
            super().__setitem__(key, value)

class MultiDict(_Base):
    pass

class CIMultiDict(_Base):
    def __init__(self, *args, **kwargs):
        data = dict(*args, **kwargs)
        super().__init__({k.lower(): v for k, v in data.items()})

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def get(self, key, default=None):
        return super().get(key.lower(), default)

    def getall(self, key: str):
        return super().getall(key.lower())
