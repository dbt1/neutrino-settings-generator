.PHONY: venv init lint test build convert-sample docker-build docker-run clean smoke qa

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

smoke:
	. $(VENV)/bin/activate && e2neutrino convert --input $(SAMPLE_PROFILE) --output out/smoke --api-version 4 --strict --abort-on-empty

qa:
	. $(VENV)/bin/activate && e2neutrino ingest --config examples/sources.official.yml --out work/ingest --cache work/cache
	find work/ingest -type d -name enigma2 -print > work/profiles.txt
	. $(VENV)/bin/activate && while read -r profile; do \
		source_id=$$(basename $$(dirname $$(dirname "$$profile"))); \
		profile_id=$$(basename $$(dirname "$$profile")); \
		out_dir="out/$${source_id}/$${profile_id}/ALL"; \
		e2neutrino convert --input "$$profile" --output "$$out_dir" --api-version 4 --strict --abort-on-empty; \
	done < work/profiles.txt

docker-build:
	docker build -t e2neutrino:latest .

docker-run:
	docker run --rm -v "$$(pwd)/out:/out" e2neutrino:latest --help

clean:
	rm -rf $(VENV) build dist out *.egg-info
