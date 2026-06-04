# syntax=docker/dockerfile:1
# Multi-stage, non-root. Build context = repo root (so lib/ is available):
#   docker build -f services/mcp-arize/Dockerfile -t mcp-arize .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/mcp-arize/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY lib/ ./lib/
COPY services/mcp-arize/app/ ./app/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8081
USER app
EXPOSE 8081
CMD ["sh", "-c", "exec uvicorn app.server:app --host 0.0.0.0 --port ${PORT}"]
