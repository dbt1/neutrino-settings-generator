.PHONY: help install lint test typecheck format convert-sample docker-build docker-run update-golden

PYTHON ?= python
PACKAGE := e2neutrino
SAMPLE_PROFILE := samples/enigma2_profile_example
SAMPLE_OUTPUT := build/sample-output

help:
	@echo "Targets:"
	@echo "  install         Install package with dev extras"
	@echo "  lint            Run ruff linting"
	@echo "  typecheck       Run mypy type checking"
	@echo "  test            Execute pytest suite"
	@echo "  format          Auto-format with ruff"
	@echo "  convert-sample  Convert sample Enigma2 profile"
	@echo "  docker-build    Build multi-stage Docker image"
	@echo "  docker-run      Run converter inside Docker (sample)"
	@echo "  update-golden   Refresh golden XML fixtures (use with care)"

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	ruff check $(PACKAGE) tests

typecheck:
	mypy $(PACKAGE)

test:
	$(PYTHON) -m pytest

format:
	ruff format $(PACKAGE) tests

convert-sample:
	rm -rf $(SAMPLE_OUTPUT)
	$(PYTHON) -m e2neutrino --version >/dev/null
	e2neutrino convert --input $(SAMPLE_PROFILE) --output $(SAMPLE_OUTPUT)
	@echo "Sample output written to $(SAMPLE_OUTPUT)"

docker-build:
	docker build -t e2neutrino:latest .

docker-run: docker-build
	docker run --rm -v $$(pwd)/$(SAMPLE_PROFILE):/input -v $$(pwd)/$(SAMPLE_OUTPUT):/output e2neutrino:latest \
		e2neutrino convert --input /input --output /output

update-golden:
	rm -rf $(SAMPLE_OUTPUT)
	e2neutrino convert --input tests/fixtures/enigma_golden --output $(SAMPLE_OUTPUT)
	cp $(SAMPLE_OUTPUT)/services.xml tests/fixtures/golden/services.xml
	cp $(SAMPLE_OUTPUT)/bouquets.xml tests/fixtures/golden/bouquets.xml
