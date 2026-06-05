# frontend — OpsSentinel dashboard (Next.js App Router)

The management & observability console for engineering directors and SREs. **Read-only**: it renders
the incident state the agent produces and the reliability telemetry — it never approves or executes
remediations (that is the Slack/agent path).

> **Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind v4 · `output: 'standalone'`.
> **Heed [`AGENTS.md`](AGENTS.md)** — this Next.js has breaking changes; read `node_modules/next/dist/docs/`
> before editing. Notably: middleware is now **`proxy`**, and `cookies()`/`params`/`searchParams` are **async**.

## Surface (server-rendered)

| Route | View |
|---|---|
| `/login` | Google Identity Services sign-in |
| `/incidents` | Incident list + status/severity filters |
| `/incidents/[id]` | SSR detail: root cause, evidence, recommendation, audit timeline, **Phoenix trace deep-link** |
| `/reliability` | MTTD, MTTR, triage accuracy, correlation precision, approval rate, calibration, autonomy coverage |
| `/health` | Connected-sources status |

## Security

- **Google Identity Services** ID token obtained client-side → POSTed to `/api/auth` → **cryptographically
  verified server-side** with `google-auth-library` (audience = `google-oauth-client-id`).
- The verified **`sub`** keys an **HMAC-signed, httpOnly** session cookie (never client-readable);
  role separation (`director`/`sre`) is derived from the verified token, not client state.
- Server-side guard in `app/(dashboard)/layout.tsx` redirects unauthenticated requests to `/login`.
- All views fetch **server-side**; loading + error boundaries keep the client exception-free.

## Run

```bash
# Local (mock data — no live agent needed):
npm install
npm run dev            # http://localhost:3000  (set NEXT_PUBLIC/GOOGLE_OAUTH_CLIENT_ID to sign in)
npm run build          # produces .next/standalone for the Docker image

# Live mode reads the Phase-1 Postgres incident store:
OPSSENTINEL_DATA_MODE=live DATABASE_URL=postgresql://... npm run dev
```

## Container & deploy

Multi-stage **Alpine** Dockerfile builds the **standalone** output and runs as **non-root**
(`docker build -t opssentinel-frontend ./frontend`). Deployed to Cloud Run as
`opssentinel-frontend` behind the Phase-1 **Serverless NEG + L7 LB + Cloud CDN**
(see [`infra/cloud-run/frontend.tf`](../infra/cloud-run/frontend.tf) and
[`infra/networking`](../infra/networking)). Secrets (`google-oauth-client-id`, `database-url`,
`session-secret`) are injected from Secret Manager; the SA is least-privilege
([`infra/iam/phase4.tf`](../infra/iam/phase4.tf)).
