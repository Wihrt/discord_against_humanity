# ---------------------------------------------------------------------------
# Stage 1 – Build (install deps in a virtual-env with uv)
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (maximise layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and finalise install
COPY src/ src/
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 – Runtime (minimal image, no uv / build tools)
# ---------------------------------------------------------------------------
FROM python:3.14-slim-bookworm AS runtime

# Security: run as non-root
RUN groupadd --gid 1000 bot && \
    useradd --uid 1000 --gid bot --shell /bin/bash --create-home bot

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VALKEY_HOST=valkey \
    VALKEY_PORT=6379

WORKDIR /app

# Copy only the virtual-env from the builder stage
COPY --from=builder --chown=bot:bot /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

USER bot

CMD ["python", "-m", "discord_against_humanity"]
