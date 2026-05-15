# AGENTS Guide for `asgi-tools/core`

## Stack

- Python `>=3.10,<4` — package: `asgi_tools` — async: asyncio, trio, curio
- Tests: `pytest`, `pytest-aio`, `pytest-benchmark`
- Quality: `ruff`, `black`, `mypy`, `pre-commit`
- Build: `setuptools`, optional Cython (`.pyx`)

## Commands

```bash
make                    # venv + install .[tests,dev,examples] + pre-commit
pytest                  # full suite (-xsv tests via pyproject.toml)
pytest tests/test_x.py::test_y   # single test
pytest -k "keyword"     # keyword selection
ruff check asgi_tools && mypy && pytest   # CI parity
make docs               # build docs
```

## Layout

`asgi_tools/` | `tests/` | `examples/` | `docs/` | `pyproject.toml`

## Code Style

- `from __future__ import annotations` at top; imports: stdlib → third-party → local
- Max line 100; Black formatting; snake_case, PascalCase, UPPER_SNAKE
- Type public APIs with aliases from `asgi_tools/types.py`; `TYPE_CHECKING` for typing-only imports
- ASGI signatures: `(scope, receive, send)`; no blocking in async paths
- Return `Response` or values accepted by `parse_response`
- Prefer project exceptions from `asgi_tools.errors`; preserve exception chaining
- Tests: `async def test_<feature>_<scenario>`; use fixtures from `tests/conftest.py`

## Working Agreement

- Minimal, targeted changes; no unrelated refactors
- Preserve public API behavior unless task requires otherwise
- When uncertain, follow nearby patterns and existing tests
- Ruff select `["ALL"]` with curated ignores; conventional commits (`.git-commits.yaml`)
