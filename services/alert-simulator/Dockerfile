# syntax=docker/dockerfile:1
# Multi-stage, non-root. Build context = repo root (so lib/ is available):
#   docker build -f services/alert-simulator/Dockerfile -t alert-simulator .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/alert-simulator/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY lib/ ./lib/
COPY services/alert-simulator/app/ ./app/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
# Default to emitting one signal; override the command for `storm` mode.
ENTRYPOINT ["python", "-m", "app.main"]
CMD ["signal"]
