# Builder Stage
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# Runner Stage
FROM python:3.12-slim-bookworm AS runner

COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app