# syntax=docker/dockerfile:1
# Multi-stage build (Dockerfile, not Buildpacks) on Alpine, copying the Next.js standalone output
# and running as a NON-ROOT user — the four mandatory properties from the spec.
#   docker build -t opssentinel-frontend ./frontend

# ── deps ─────────────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ── build (standalone output traced by the compiler) ─────────────────────────
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── runtime (minimal, non-root) ──────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Create and run as an unprivileged user (mitigates privilege escalation).
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# Standalone server + the static/public assets it needs.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
