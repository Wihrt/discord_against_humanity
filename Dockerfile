# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build: resolve the locked dependencies into a virtual environment with uv
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

FROM python:3.14-slim-trixie@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8 AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_DEV=1

WORKDIR /app

# Dependencies first, so that code changes do not invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# ---------------------------------------------------------------------------
# Runtime: no uv, no sources, unprivileged, compatible with a read-only root
# filesystem and the Kubernetes "restricted" Pod Security Standard.
# ---------------------------------------------------------------------------
FROM python:3.14-slim-trixie@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8 AS runtime

# Owned by root and read-only for the bot user: the code cannot be altered.
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

# Numeric UID/GID so that Kubernetes can enforce runAsNonRoot.
USER 10001:10001

ENTRYPOINT ["discord-against-humanity"]
CMD ["run"]
