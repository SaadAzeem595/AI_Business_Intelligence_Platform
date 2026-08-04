# Multi-stage build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Inject uv package manager binary directly into container builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies list
COPY pyproject.toml .

# Compile and install dependencies system-wide (eliminates virtualenv inside container)
RUN uv pip install --system --no-cache -r pyproject.toml

# Final lightweight stage
FROM python:3.12-slim

WORKDIR /app

# Copy python dependencies packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source folders
COPY app app
COPY run.py run.py

# Setup non-root execution user for security hardening
RUN groupadd -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -d /app -s /sbin/nologin appuser && \
    mkdir -p storage && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["python", "run.py"]
