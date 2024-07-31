VIRTUAL_ENV 	?= env
PACKAGE		?= asgi_tools

all: $(VIRTUAL_ENV)

$(VIRTUAL_ENV): pyproject.toml .pre-commit-config.yaml
	@[ -d $(VIRTUAL_ENV) ] || python -m venv $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -e .[tests,dev,examples,docs]
	@$(VIRTUAL_ENV)/bin/pre-commit install
	@touch $(VIRTUAL_ENV)

VPART	?= minor

.PHONY: release
release: $(VIRTUAL_ENV)
	git checkout develop
	git pull
	git checkout master
	git pull
	git merge develop
	$(VIRTUAL_ENV)/bin/bump2version $(VPART)
	git checkout develop
	git merge master
	git push --tags origin develop master

.PHONY: minor
minor:
	make release VPART=minor

.PHONY: patch
patch:
	make release VPART=patch

.PHONY: major
major:
	make release VPART=major


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
	$(VIRTUAL_ENV)/bin/uvicorn --loop asyncio --port 5000 --reload examples.$(EXAMPLE):app

$(PACKAGE)/%.c: $(PACKAGE)/%.pyx
	$(VIRTUAL_ENV)/bin/cython -a $<

cyt: $(PACKAGE)/multipart.c $(PACKAGE)/forms.c

compile: cyt
	$(VIRTUAL_ENV)/bin/python setup.py build_ext --inplace
