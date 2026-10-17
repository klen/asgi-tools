PACKAGE		?= asgi_tools

all: .venv

.venv: pyproject.toml uv.lock .pre-commit-config.yaml
	@uv sync --frozen --extra tests --extra dev --extra examples
	@.venv/bin/pre-commit install
	@touch .venv


.PHONY: clean
# target: clean - Display callable targets
clean:
	rm -rf build/ dist/ docs/_build *.egg-info $(PACKAGE)/*.c $(PACKAGE)/*.so $(PACKAGE)/*.html
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR) -name "__pycache__" | xargs rm -rf

.PHONY: docs
docs: .venv
	rm -rf docs/_build/html
	make -C docs html

outdated: .venv
	uv tree --outdated

upgrade: .venv
	uv lock --upgrade
	uv sync --all-extras


LATEST_BENCHMARK = $(shell ls -t .benchmarks/* | head -1 | head -c4)
test t: cyt .venv
	.venv/bin/pytest tests --benchmark-autosave --benchmark-compare=$(LATEST_BENCHMARK)

lint: .venv
	.venv/bin/mypy
	.venv/bin/ruff check


mypy: .venv
	.venv/bin/mypy


EXAMPLE = rates

example: .venv
	.venv/bin/uvicorn --loop asyncio --reload examples.$(EXAMPLE):app

example-rates:
	make example EXAMPLE=rates

example-request-response:
	make example EXAMPLE=request_response

example-request-response-middleware:
	make example EXAMPLE=request_response_middleware

example-router-middleware:
	make example EXAMPLE=router_middleware

example-sse:
	make example EXAMPLE=sse

example-static:
	make example EXAMPLE=static

example-websocket:
	make example EXAMPLE=websocket

$(PACKAGE)/%.c: $(PACKAGE)/%.pyx
	.venv/bin/cython -a $<

cyt: $(PACKAGE)/multipart.c $(PACKAGE)/forms.c

compile: cyt
	.venv/bin/python setup.py build_ext --inplace

# ======================
#  Bump version
# ======================

RELEASE	?= minor

.PHONY: release
# target: release - Bump version
release:
	@echo "Starting release process (bumping $(RELEASE) version)..."
	@git checkout main
	@git pull
	@git checkout develop
	@git pull
	@echo "Bumping version and creating release commit and tag..."
	@uvx bump-my-version bump $(RELEASE)
	@echo "Version bumped to `uvx bump-my-version show current_version`."
	@uv lock
	@echo "Committing version bump and creating tag..."
	@VERSION="$$(uvx bump-my-version show current_version)"; \
		{ \
			printf 'build(release): %s\n\n' "$$VERSION"; \
			printf 'Changes:\n\n'; \
			git log --oneline --pretty=format:'%s [%an]' main..develop | grep -Evi 'github|^Merge' || true; \
		} | git commit -a -F -
	@echo "Merging changes between branches..."
	@git checkout main
	@git merge develop
	@VERSION="$$(uvx bump-my-version show current_version)"; \
		git push origin main; \
		git tag -a "$$VERSION" -m "$$VERSION"; \
		git push origin tag "$$VERSION"
	@git checkout develop
	@git merge main
	@git push origin develop
	@echo "Release process complete for `uvx bump-my-version show current_version`"

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release RELEASE=patch

.PHONY: major
major:
	make release RELEASE=major

version v:
	@uvx bump-my-version show current_version
