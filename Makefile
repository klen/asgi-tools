VIRTUAL_ENV 	?= env
PACKAGE		?= asgi_tools

all: $(VIRTUAL_ENV)

$(VIRTUAL_ENV): setup.cfg
	@[ -d $(VIRTUAL_ENV) ] || python -m venv $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -e .[build,tests,examples,docs]
	@touch $(VIRTUAL_ENV)

VERSION	?= minor

.PHONY: version
version:
	$(VIRTUAL_ENV)/bin/bump2version $(VERSION)
	git checkout master
	git pull
	git merge develop
	git checkout develop
	git push origin develop master
	git push --tags

.PHONY: minor
minor:
	make version VERSION=minor

.PHONY: patch
patch:
	make version VERSION=patch

.PHONY: major
major:
	make version VERSION=major


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


mypy: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/mypy asgi_tools


EXAMPLE = rates

example: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/uvicorn --port 5000 --reload examples.$(EXAMPLE):app

$(PACKAGE)/%.c: $(PACKAGE)/%.pyx
	$(VIRTUAL_ENV)/bin/cython -a $<

cyt: $(PACKAGE)/request.c $(PACKAGE)/multipart.c $(PACKAGE)/forms.c

compile: cyt
	$(VIRTUAL_ENV)/bin/python setup.py build_ext --inplace
