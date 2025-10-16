FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY . .
RUN pip install --upgrade pip \
    && pip install build \
    && python -m build

FROM python:3.11-slim AS runtime
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl
ENTRYPOINT ["e2neutrino"]
CMD ["--help"]
