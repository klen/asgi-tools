# AGENTS Guide for `asgi-tools/core`

Repository guide for agentic coding tools working in this project.

## Project Snapshot

- Language: Python (`>=3.10,<4`)
- Main package: `asgi_tools`
- Tests: `pytest`, `pytest-aio[curio,trio]`, `pytest-benchmark`
- Quality: `ruff`, `black`, `mypy`, `pre-commit`
- Build: `setuptools`, optional Cython extensions (`asgi_tools/*.pyx`)
- Async targets: asyncio, trio, curio, optional uvloop

## Setup

```bash
python -m venv env
env/bin/pip install -e .[tests,dev,examples]
env/bin/pre-commit install
```

Alternative bootstrap:

```bash
make
```

## Build Commands

- Build source distribution: `python -m build --sdist`
- Build cythonized extensions in place: `make compile`
- Generate C from pyx: `make cyt`
- Force pure Python build: `ASGI_TOOLS_NO_EXTENSIONS=1 python -m build --sdist`

## Lint / Format / Typecheck

- Lint target: `make lint`
- Ruff: `ruff check asgi_tools`
- Black: `black asgi_tools tests`
- Mypy: `mypy`
- All hooks: `pre-commit run --all-files`

## Test Commands (Important)

- Full suite: `pytest`
- Make target with benchmark compare: `make test`
- Single file: `pytest tests/test_request.py`
- Single test function: `pytest tests/test_request.py::test_json`
- Single class-like group by keyword: `pytest -k "app_middleware"`
- Select by keyword: `pytest -k "websocket and not benchmark"`
- Single benchmark test: `pytest tests/test_benchmarks.py::test_benchmark_name`
- Stop after first failure (explicit): `pytest -x tests/test_app.py`

Pytest defaults from `pyproject.toml`:

- `addopts = "-xsv tests"`
- `-x`: stop on first failure
- `-s`: show stdout/stderr
- `-v`: verbose output
- For targeted runs, prefer explicit file path or node id.

## Docs Commands

```bash
pip install -r docs/requirements.txt
make docs
```

or:

```bash
make -C docs html
```

## CI Parity Commands

- CI installs tests extras: `pip install .[tests]`
- CI lint step: `ruff check asgi_tools`
- CI typecheck step: `mypy` (non-PyPy jobs)
- CI test step: `pytest`
- For local parity, run the same order: ruff -> mypy -> pytest.

## Repository Layout (Quick)

- Core package: `asgi_tools/`
- Test suite: `tests/`
- Examples: `examples/`
- Docs source: `docs/`
- Build metadata: `pyproject.toml`, `setup.py`, `Makefile`

## Code Style Guidelines

### Imports

- Keep `from __future__ import annotations` at module top.
- Import order: stdlib, third-party, local package.
- Use `TYPE_CHECKING` for typing-only imports.
- Prefer package-local absolute imports when it matches nearby code.

### Formatting

- Max line length: 100.
- Use Black formatting; avoid manual style tweaks.
- Keep functions focused and straightforward.
- Prefer guard clauses and early returns over nested conditionals.

### Types

- Type public APIs and non-trivial internals.
- Reuse aliases from `asgi_tools/types.py` (`TASGIScope`, `TASGIReceive`, etc.).
- Use `TypeVar` and overloads where they clarify behavior.
- Use `cast` sparingly.

### Naming

- Variables/functions/modules: `snake_case`
- Classes/exceptions: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Tests: behavior-oriented names (`test_<feature>_<scenario>`)

### Error Handling

- Prefer project exceptions from `asgi_tools.errors`.
- Preserve exception chaining (`raise ... from exc`) when wrapping errors.
- Map expected failures to explicit responses in app/middleware flow.
- Avoid broad `except` unless it is an intentional framework boundary.

### Async and ASGI Conventions

- Keep ASGI signatures explicit: `(scope, receive, send)`.
- Avoid blocking operations in async paths.
- Use `asgi_tools._compat` helpers for runtime-portable async behavior.
- Preserve asyncio/trio/curio compatibility in shared async utilities.

### Request/Response Behavior

- Return `Response` objects or values accepted by `parse_response`.
- Preserve defaults for content type, encoding, and headers.
- Keep cookie/header behavior aligned with existing response classes.

### Testing Expectations

- Add/update tests for behavior changes under `tests/`.
- Prefer focused unit tests over broad integration tests.
- Keep benchmark tests unless explicitly asked to remove them.
- Use existing fixtures from `tests/conftest.py` before introducing new ones.
- Match existing async test style (`async def test_*`).

## Ruff and Hooks Notes

- Ruff uses `select = ["ALL"]` plus curated ignores.
- Tests have dedicated per-file ignores in `pyproject.toml`.
- Ruff isort requires `from __future__ import annotations`.
- Pre-commit stages include `commit-msg`, `pre-commit`, `pre-push`.
- Commit messages must follow conventional commits (`.git-commits.yaml`).

## Agent Working Agreement

- Make minimal, targeted changes.
- Do not refactor unrelated code in the same patch.
- Preserve public API behavior unless task requirements explicitly change it.
- When uncertain, follow nearby patterns and existing tests.
