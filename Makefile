VIRTUAL_ENV 	?= env
PACKAGE		?= asgi_tools

all: $(VIRTUAL_ENV)

$(VIRTUAL_ENV): pyproject.toml .pre-commit-config.yaml
	@[ -d $(VIRTUAL_ENV) ] || python -m venv $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -e .[tests,dev,examples,docs]
	@$(VIRTUAL_ENV)/bin/pre-commit install
	@touch $(VIRTUAL_ENV)


.PHONY: clean
# target: clean - Display callable targets
clean:
	rm -rf build/ dist/ docs/_build *.egg-info $(PACKAGE)/*.c $(PACKAGE)/*.so $(PACKAGE)/*.html
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR) -name "__pycache__" | xargs rm -rf

.PHONY: docs
docs: $(VIRTUAL_ENV)
	rm -rf docs/_build/html
	make -C docs html

outdated: $(VIRTUAL_ENV)
	poetry show --outdated

upgrade: $(VIRTUAL_ENV)
	poetry update
	poetry install --all-extras


LATEST_BENCHMARK = $(shell ls -t .benchmarks/* | head -1 | head -c4)
test t: cyt $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/pytest tests --benchmark-autosave --benchmark-compare=$(LATEST_BENCHMARK)

lint: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/mypy
	$(VIRTUAL_ENV)/bin/ruff check


mypy: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/mypy


EXAMPLE = rates

example: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/uvicorn --loop asyncio --reload examples.$(EXAMPLE):app

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
	$(VIRTUAL_ENV)/bin/cython -a $<

cyt: $(PACKAGE)/multipart.c $(PACKAGE)/forms.c

compile: cyt
	$(VIRTUAL_ENV)/bin/python setup.py build_ext --inplace

# ======================
#  Bump version (poetry)
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
	@echo "Version bumped to `poetry version --short`."
	@poetry lock
	@echo "Committing version bump and creating tag..."
	@VERSION="$$(poetry version --short)"; \
		{ \
			printf 'build(release): %s\n\n' "$$VERSION"; \
			printf 'Changes:\n\n'; \
			git log --oneline --pretty=format:'%s [%an]' main..develop | grep -Evi 'github|^Merge' || true; \
		} | git commit -a -F -
	@echo "Merging changes between branches..."
	@git checkout main
	@git merge develop
	@VERSION="$$(poetry version --short)"; \
		git push origin main; \
		git tag -a "$$VERSION" -m "$$VERSION"; \
		git push origin tag "$$VERSION"
	@git checkout develop
	@git merge main
	@git push origin develop
	@echo "Release process complete for `poetry version --short`"

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release RELEASE=patch

.PHONY: major
major:
	make release RELEASE=major

version v:
	@poetry version --short
