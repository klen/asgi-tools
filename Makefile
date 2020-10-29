VIRTUAL_ENV 	?= env

all: $(VIRTUAL_ENV)

$(VIRTUAL_ENV): $(CURDIR)/requirements.txt $(CURDIR)/requirements-tests.txt
	@[ -d $(VIRTUAL_ENV) ] || virtualenv --python=python3 $(VIRTUAL_ENV)
	@$(VIRTUAL_ENV)/bin/pip install -r requirements-tests.txt
	@touch $(VIRTUAL_ENV)

VERSION	?= minor

.PHONY: version
version:
	pip install bump2version
	bump2version $(VERSION)
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
	@pip install twine wheel
	@python setup.py bdist_wheel
	@twine upload dist/*


test t: $(VIRTUAL_ENV)
	$(VIRTUAL_ENV)/bin/pytest tests.py
