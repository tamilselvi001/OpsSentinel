# syntax=docker/dockerfile:1
# Multi-stage, non-root. Build context = repo root (so lib/ is available):
#   docker build -f services/agent/Dockerfile -t agent .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/agent/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY lib/ ./lib/
COPY services/agent/app/ ./app/
COPY services/agent/policy/ ./policy/
COPY services/agent/prompts/ ./prompts/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
USER app
# The agent is a Pub/Sub pull worker; it also serves /health on $PORT for Cloud Run liveness.
EXPOSE 8080
CMD ["python", "-m", "app.main"]
