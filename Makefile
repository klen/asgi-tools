VIRTUAL_ENV 	?= env
PACKAGE		?= asgi_tools

all: $(VIRTUAL_ENV)

$(VIRTUAL_ENV): pyproject.toml .pre-commit-config.yaml
	@[ -d $(VIRTUAL_ENV) ] || python -m venv $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -e .[tests,dev,examples,docs]
	@$(VIRTUAL_ENV)/bin/pre-commit install
	@touch $(VIRTUAL_ENV)

VERSION	?= minor
MAIN_BRANCH = master
STAGE_BRANCH = develop

.PHONY: release
# target: release - Bump version
release:
	git checkout $(MAIN_BRANCH)
	git pull
	git checkout $(STAGE_BRANCH)
	git pull
	$(VIRTUAL_ENV)/bin/bump2version $(VERSION)
	git checkout $(MAIN_BRANCH)
	git merge $(STAGE_BRANCH)
	git checkout $(STAGE_BRANCH)
	git merge $(MAIN_BRANCH)
	@git -c push.followTags=false push origin $(STAGE_BRANCH) $(MAIN_BRANCH)
	@git push --tags origin

.PHONY: minor
minor:
	make release VERSION=minor

.PHONY: patch
patch:
	make release VERSION=patch

.PHONY: major
major:
	make release VERSION=major


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


LATEST_BENCHMARK = $(shell ls -t .benchmarks/* | head -1 | head -c4)
test t: cyt $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/pytest tests --benchmark-autosave --benchmark-compare=$(LATEST_BENCHMARK)

lint: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/mypy
	$(VIRTUAL_ENV)/bin/ruff $(PACKAGE)


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
