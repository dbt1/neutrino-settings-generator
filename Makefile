.PHONY: venv init lint test build convert-sample docker-build docker-run clean smoke qa

VENV ?= .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)
PIP := $(if $(wildcard $(VENV_PIP)),$(VENV_PIP),pip)
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
PYTEST := $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
MYPY := $(if $(wildcard $(VENV_BIN)/mypy),$(VENV_BIN)/mypy,mypy)
E2NEUTRINO := $(if $(wildcard $(VENV_BIN)/e2neutrino),$(VENV_BIN)/e2neutrino,e2neutrino)
PACKAGE := e2neutrino
SAMPLE_PROFILE := samples/enigma2_profile_example
SAMPLE_OUTPUT := out/sample

venv:
	python3 -m venv $(VENV)

init: venv
	$(VENV_PIP) install --upgrade pip wheel
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install -e . --no-deps

lint:
	$(RUFF) check .

test:
	$(PYTEST) -q

build:
	$(PYTHON) -m build

convert-sample:
	$(E2NEUTRINO) convert --input $(SAMPLE_PROFILE) --output $(SAMPLE_OUTPUT) --api-version 4
	@echo "Sample output written to $(SAMPLE_OUTPUT)"

smoke:
	$(E2NEUTRINO) convert --input $(SAMPLE_PROFILE) --output out/smoke --api-version 4 --strict --abort-on-empty

qa:
	$(E2NEUTRINO) ingest --config examples/sources.official.yml --out work/ingest --cache work/cache
	find work/ingest -type d -name enigma2 -print > work/profiles.txt
	@while read -r profile; do \
		source_id=$$(basename $$(dirname $$(dirname "$$profile"))); \
		profile_id=$$(basename $$(dirname "$$profile")); \
		out_dir="out/$${source_id}/$${profile_id}/ALL"; \
		$(E2NEUTRINO) convert --input "$$profile" --output "$$out_dir" --api-version 4 --strict --abort-on-empty; \
	done < work/profiles.txt

docker-build:
	docker build -t e2neutrino:latest .

docker-run:
	docker run --rm -v "$$(pwd)/out:/out" e2neutrino:latest --help

clean:
	rm -rf $(VENV) build dist out *.egg-info
