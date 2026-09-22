FROM python:3.12-slim

WORKDIR /app

# Inject uv package manager binary directly into container builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies list
COPY pyproject.toml .

# Create virtual environment and install dependencies
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv venv /opt/venv && uv pip install --no-cache -r pyproject.toml

# Copy source folders and migration definitions
COPY app app
COPY run.py run.py
COPY alembic alembic
COPY alembic.ini alembic.ini

# Setup non-root execution user for security hardening
RUN groupadd -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -d /app -s /sbin/nologin appuser && \
    mkdir -p storage uploads && \
    chown -R appuser:appgroup /app /opt/venv

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips=*"]
