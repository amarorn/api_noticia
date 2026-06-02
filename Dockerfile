FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

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

RUN pip install --upgrade pip && \
    pip install . && \
    pip install scikit-learn

EXPOSE 7860

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
