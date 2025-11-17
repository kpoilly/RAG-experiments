# ========== linter ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS linter

WORKDIR /app
COPY pyproject.toml .
RUN uv venv && \
    uv pip install .[dev]
ENV PATH="/app/.venv/bin:$PATH"

COPY . .


# ========== builder ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev -qq


# ========== runner ==========
FROM python:3.12-slim-bookworm AS runner

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY main.py .

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]