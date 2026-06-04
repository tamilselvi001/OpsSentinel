# syntax=docker/dockerfile:1
# Multi-stage, non-root. Build context = repo root (so lib/ is available):
#   docker build -f services/mcp-elastic/Dockerfile -t mcp-elastic .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY services/mcp-elastic/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY lib/ ./lib/
COPY services/mcp-elastic/app/ ./app/
COPY services/mcp-elastic/index/ ./index/

# Pre-download the embedding model into the image so first request isn't slow / network-bound.
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" \
    && chown -R app:app /app/.cache

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080
USER app
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.server:app --host 0.0.0.0 --port ${PORT}"]
