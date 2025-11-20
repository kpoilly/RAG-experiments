# ========== linter ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS linter
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/dev-venv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --only-group dev --no-install-project
ENV PATH="/opt/dev-venv/bin:$PATH"

COPY . .


# ========== builder ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0


ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev


# ========== runner ==========
FROM python:3.12-slim-bookworm AS runner

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]