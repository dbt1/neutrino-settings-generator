.PHONY: venv init lint test build convert-sample docker-build docker-run clean

VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PACKAGE := e2neutrino
SAMPLE_PROFILE := samples/enigma2_profile_example
SAMPLE_OUTPUT := out/sample

venv:
	python3 -m venv $(VENV)

init: venv
	. $(VENV)/bin/activate && pip install --upgrade pip wheel
	. $(VENV)/bin/activate && pip install -r requirements.txt
	. $(VENV)/bin/activate && pip install -e . --no-deps

lint:
	. $(VENV)/bin/activate && ruff check .

test:
	. $(VENV)/bin/activate && pytest -q

build:
	. $(VENV)/bin/activate && python -m build

convert-sample:
	. $(VENV)/bin/activate && e2neutrino convert --input $(SAMPLE_PROFILE) --output $(SAMPLE_OUTPUT) --api-version 4
	@echo "Sample output written to $(SAMPLE_OUTPUT)"

docker-build:
	docker build -t e2neutrino:latest .

docker-run:
	docker run --rm -v "$$(pwd)/out:/out" e2neutrino:latest --help

clean:
	rm -rf $(VENV) build dist out *.egg-info
