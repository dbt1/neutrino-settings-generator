# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS build
ENV PIP_NO_CACHE_DIR=1
WORKDIR /workspace
COPY pyproject.toml README.md requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install build
COPY . .
RUN pip install -e ".[dev]" \
    && ruff check e2neutrino tests \
    && mypy e2neutrino \
    && pytest \
    && python -m build

FROM python:3.11-slim AS runtime
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY --from=build /workspace/dist /dist
RUN pip install /dist/*.whl
COPY samples ./samples
COPY examples ./examples
ENTRYPOINT ["e2neutrino"]
CMD ["--help"]
