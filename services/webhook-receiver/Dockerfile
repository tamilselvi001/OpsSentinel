# syntax=docker/dockerfile:1
# Multi-stage build. Build context MUST be the repo root so `lib/` is available:
#   docker build -f services/webhook-receiver/Dockerfile -t webhook-receiver .

# ── Builder: install deps into an isolated prefix ────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/webhook-receiver/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime: slim, non-root ──────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
# Create an unprivileged user; the service never needs root.
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY lib/ ./lib/
COPY services/webhook-receiver/app/ ./app/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

USER app
EXPOSE 8080

# Cloud Run provides $PORT; default to 8080 locally.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
