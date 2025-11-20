# ========== linter ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS linter
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/opt/dev-venv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --only-group dev --no-install-project
ENV PATH="/opt/dev-venv/bin:$PATH"

COPY models.py .
COPY utils.py .
COPY config.py .
COPY main.py .
COPY ingestion.py .
COPY ingestion_utils.py .
COPY retriever.py .


# ========== builder ==========
FROM ghcr.io/astral-sh/uv:0.9.9-python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
ARG USE_GPU=false

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    if [ "$USE_GPU" = "true" ]; then \
        echo "Building for GPU..." && \
        uv sync --locked --no-install-project --no-dev --extra gpu -qq; \
    else \
        echo "Building for CPU..." && \
        uv sync --locked --no-install-project --no-dev --extra cpu -qq; \
    fi


# ========== runner ==========
FROM python:3.12-slim-bookworm AS runner

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY models.py .
COPY utils.py .
COPY config.py .
COPY main.py .
COPY ingestion.py .
COPY ingestion_utils.py .
COPY retriever.py .
COPY ./prompts ./prompts/

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]