FROM python:3.12-slim

# Ensure pipefail is set for any RUN using pipes (fixes DL4006)
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install uv for fast, deterministic dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libmagic1 \
    tzdata \
    netcat-openbsd \
    sqlite3 \
    libsqlite3-dev \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

# Install dependencies first (cached layer unless pyproject.toml/uv.lock change)
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project

COPY . /app

# Create data directory for SQLite database
RUN mkdir -p /app/data \
 && chown -R app:app /app \
 && chmod +x /app/scripts/docker-entrypoint.sh /app/scripts/db_upgrade.py

USER app

ENV WEB_WORKERS=4 \
    WEB_LOGLEVEL=info

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn","fitness.main:app","--host","0.0.0.0","--port","8000"]
