# docker/Dockerfile
# Multi-stage build: slim production image for the ETL pipeline

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Only the runtime OS packages needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 pipeline && \
    mkdir -p /app/logs && \
    chown -R pipeline:pipeline /app

# Non-root user for security
USER pipeline

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/pipeline/.local
ENV PATH=/home/pipeline/.local/bin:$PATH

# Copy source code
COPY --chown=pipeline:pipeline . .

# Logs directory
RUN mkdir -p /app/logs

# Health check — verifies the pipeline module is importable
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "from pipelines.etl_pipeline import run; print('OK')" || exit 1

CMD ["python", "-m", "pipelines.etl_pipeline"]
