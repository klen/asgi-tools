VIRTUAL_ENV 	?= env

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
	rm -rf build/ dist/ docs/_build *.egg-info
	find $(CURDIR) -name "*.py[co]" -delete
	find $(CURDIR) -name "*.orig" -delete
	find $(CURDIR)/$(MODULE) -name "__pycache__" | xargs rm -rf

.PHONY: register
# target: register - Register module on PyPi
register:
	@python setup.py register

.PHONY: upload
# target: upload - Upload module on PyPi
upload: clean
	@python setup.py bdist_wheel
	@$(VIRTUAL_ENV)/bin/twine upload dist/*


test t: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/pytest tests


mypy: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/mypy asgi_tools


example: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/uvicorn --port 5000 --reload examples.rates:app


example-websocket: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/uvicorn --port 5000 --reload examples.websocket:app

.PHONY: docs
docs: $(VIRTUAL_ENV)
	rm -rf docs/_build/html
	make -C docs html
