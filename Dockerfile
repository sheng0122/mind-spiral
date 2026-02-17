## Stage 1: 安裝依賴
FROM python:3.12-slim AS builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./

# 只安裝依賴到 .venv，不安裝專案本身
RUN uv venv .venv && uv sync --no-dev --frozen --no-install-project 2>/dev/null || uv sync --no-dev --no-install-project

## Stage 2: Runtime（只複製需要的東西）
FROM python:3.12-slim

WORKDIR /app

# 從 builder 複製已安裝的 venv
COPY --from=builder /app/.venv /app/.venv

# 複製程式碼
COPY pyproject.toml ./
COPY engine/ ./engine/
COPY config/ ./config/
COPY schemas/ ./schemas/

# 安裝專案本身（只做 editable install，不重裝依賴）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000 8001

CMD ["sh", "-c", "uvicorn engine.api:app --host 0.0.0.0 --port 8000 & python -m engine.mcp_server --http & wait"]
