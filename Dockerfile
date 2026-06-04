FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    LAKE_ROOT=/data/lake \
    WC_ARTIFACT_DIR=/data/lake/artifacts/wc_predictor

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api ./api
COPY ingest ./ingest
COPY models ./models
COPY pipelines ./pipelines
COPY schemas ./schemas
COPY config.py ./
COPY data/sources.yaml ./data/sources.yaml
COPY data/rounds ./data/rounds
COPY data/wc ./data/wc
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN pip install --upgrade pip && \
    pip install . && \
    pip install scikit-learn && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
