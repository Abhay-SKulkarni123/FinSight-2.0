# syntax=docker/dockerfile:1

# ---- Stage 1: build dependencies ----
FROM python:3.10-slim AS builder

WORKDIR /app

# System deps needed to build psycopg2 and scientific Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: runtime image ----
FROM python:3.10-slim

WORKDIR /app

# Runtime-only system deps (libpq5, not the full -dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash finsight

# Copy installed Python packages from the builder stage
COPY --from=builder /root/.local /home/finsight/.local

ENV PATH=/home/finsight/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=core.settings

COPY --chown=finsight:finsight . .

# Directory for joblib-cached ML models — must be writable at runtime
RUN mkdir -p /app/main/ml_cache /app/staticfiles \
    && chown -R finsight:finsight /app

USER finsight

# Collect static files at build time (uses dummy SECRET_KEY since this
# step doesn't touch the database or need real secrets)
RUN SECRET_KEY=build-time-only-not-for-runtime \
    DEBUG=False \
    python manage.py collectstatic --noinput

EXPOSE 8000

# Healthcheck hits the home page; Django must be able to respond with 200
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
