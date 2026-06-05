# OpsSentinel — Manual Setup Guide (the things only YOU can do)

This guide lists every step **you** must do by hand before the AI agent can run
`PROMPTS/06-phase6-integration-validation-and-fidelity.md`. The agent cannot install software,
create accounts, or generate API keys for you — those are here.

Work top to bottom. Check the box as you finish each item. Most of this is a one-time setup of
**~1–2 hours**. You are on **Windows**, so commands assume **PowerShell** or **Git Bash**.

> **Legend:** 🟥 = required before the agent can start · 🟦 = required for the Slack demo step ·
> 🟨 = optional, only for deploying to Google Cloud later.

---

## 0. 🟥 CRITICAL FIRST — protect your secrets (2 minutes)

Right now your repo's `.gitignore` does **not** ignore secret files. If you create a `.env` with
real API keys and commit it, those keys get **published to your public GitHub repo**. Fix this
before you create any secrets.

Open the file `.gitignore` in the project root and make sure it contains these lines (add any that
are missing):

```
# Secrets — never commit
.env
.env.*
!.env.example
*.pem
*.key
*-key.json
service-account*.json
credentials*.json

# Terraform state (can contain secrets)
.terraform/
*.tfstate
*.tfstate.*
*.tfvars

# Build artifacts
node_modules/
.next/
.venv/
__pycache__/
```

Then verify it works (Git Bash):

```bash
git check-ignore .env          # must print:  .env
```

If it prints `.env`, you are safe. **Do not skip this.**

- [ ] `.gitignore` updated and `git check-ignore .env` prints `.env`

---

## 1. 🟥 Install the local tools

You already have **Python 3.11** and **Node.js 24 + npm**. You still need:

### 1a. Docker Desktop (required — this runs the whole stack)
- Download: https://www.docker.com/products/docker-desktop/
- Install, restart if asked, then **open Docker Desktop and wait until it says "Running".**
- Verify (PowerShell): `docker version` and `docker compose version` should both print versions.

- [ ] Docker Desktop installed and running (`docker version` works)

### 1b. GNU Make (optional but convenient)
The project has handy `make` shortcuts (`make dev`, `make validate`, …). Windows has no `make` by
default. Either:
- Install it: with **Scoop** → `scoop install make`, or with **winget** →
  `winget install GnuWin32.Make`, **or**
- Skip it — the agent knows how to run the underlying `docker compose` / `python` commands directly.

- [ ] (optional) `make --version` works, OR you've decided to let the agent use direct commands

### 1c. Terraform (needed later, for Task 6 — not for the first run)
- Download: https://developer.hashicorp.com/terraform/install (unzip, add to PATH), or
  `scoop install terraform` / `winget install HashiCorp.Terraform`.
- Verify: `terraform version`.

- [ ] (can do later) Terraform installed

### 1d. Google Cloud CLI (🟨 only if you will deploy to GCP — Task 7)
- Download: https://cloud.google.com/sdk/docs/install · then `gcloud init`.

- [ ] (optional) gcloud installed

---

## 2. 🟥 Get the API keys & credentials

You'll paste all of these into a `.env` file in Step 3. Collect them first.

### 2a. Gemini API key (the agent's brain) — 5 min
1. Go to **Google AI Studio**: https://aistudio.google.com/apikey
2. Click **Create API key** (create/choose a Google Cloud project if asked).
3. Copy the key. → goes in `.env` as `GEMINI_API_KEY`.

- [ ] `GEMINI_API_KEY` obtained

### 2b. Session secret (signs the dashboard login cookie) — 1 min
Generate a long random string. In Git Bash:
```bash
openssl rand -base64 32
```
Copy the output. → goes in `.env` as `SESSION_SECRET`.

- [ ] `SESSION_SECRET` generated

### 2c. Elasticsearch & Phoenix — nothing to do for local
For local validation, the docker-compose stack runs Elasticsearch and Phoenix for you with security
disabled, so **no keys are needed**. Leave `ELASTIC_API_KEY` / `PHOENIX_API_KEY` as the placeholder
values. (Only if you later use Elastic Cloud / Phoenix Cloud do you need real URLs + keys.)

- [ ] Nothing required (local Elastic/Phoenix come from docker-compose)

### 2d. Google OAuth Client ID (dashboard "Sign in with Google") — 10 min
1. Go to **Google Cloud Console → APIs & Services → Credentials**:
   https://console.cloud.google.com/apis/credentials
2. Pick (or create) a project, top of the page.
3. If prompted, configure the **OAuth consent screen** first: choose **External**, give the app a
   name and your email, **Save**. (You can leave it in "Testing" mode and add your own email as a
   test user.)
4. Click **+ Create Credentials → OAuth client ID**.
5. Application type: **Web application**.
6. Under **Authorized JavaScript origins**, add: `http://localhost:3000`
7. Click **Create**, then copy the **Client ID** (looks like `1234-abcd.apps.googleusercontent.com`).
   → goes in `.env` as `GOOGLE_OAUTH_CLIENT_ID`.
8. Decide who is a "director": put your Google account email in `OPSSENTINEL_DIRECTOR_EMAILS`
   (comma-separated) to land on the reliability dashboard; otherwise you're treated as an SRE.

- [ ] `GOOGLE_OAUTH_CLIENT_ID` obtained and `http://localhost:3000` added as an authorized origin

### 2e. 🟦 Slack app (the approve/reject gate) — 15 min
Only needed to demo the real Slack buttons (Task 3 of the prompt). You can do the first run without
it and approve via `make approve INCIDENT=<id>` instead — but for the full demo, set this up.

1. Go to https://api.slack.com/apps → **Create New App → From scratch**. Name it `OpsSentinel`,
   pick your workspace.
2. **OAuth & Permissions** (left menu): under **Scopes → Bot Token Scopes**, add **`chat:write`**.
3. Click **Install to Workspace**, approve. Copy the **Bot User OAuth Token** (starts with `xoxb-`).
   → `.env` as `SLACK_BOT_TOKEN`.
4. **Basic Information** (left menu): copy the **Signing Secret**. → `.env` as `SLACK_SIGNING_SECRET`.
5. In Slack, create or pick a channel (e.g. `#opssentinel`) and **invite the bot** to it
   (`/invite @OpsSentinel`). Put the channel name in `.env` as `SLACK_CHANNEL`.
6. **Interactivity** — Slack must reach your laptop to deliver button clicks. You need a public
   tunnel to `http://localhost:8083` (the slack-bot's host port):
   - Install a tunnel, e.g. **cloudflared** (`winget install Cloudflare.cloudflared`) or **ngrok**
     (https://ngrok.com/download).
   - Run it AFTER the stack is up (Task 1): `cloudflared tunnel --url http://localhost:8083`
     (or `ngrok http 8083`). Copy the public `https://…` URL it prints.
   - In the Slack app → **Interactivity & Shortcuts** → turn **On** → set **Request URL** to
     `https://<your-tunnel>/slack/interactions` → **Save**.

- [ ] `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_CHANNEL` obtained; bot invited to the channel
- [ ] (do after Task 1) tunnel running and Slack **Request URL** set to `…/slack/interactions`

---

## 3. 🟥 Create your `.env` file

1. In the project root, copy the template:
   ```bash
   cp .env.example .env          # Git Bash    (PowerShell: Copy-Item .env.example .env)
   ```
2. Open `.env` and fill in the real values you collected:
   ```
   GEMINI_API_KEY=<from 2a>
   SESSION_SECRET=<from 2b>
   GOOGLE_OAUTH_CLIENT_ID=<from 2d>
   OPSSENTINEL_DIRECTOR_EMAILS=<your email>           # optional
   SLACK_BOT_TOKEN=<from 2e>                           # for the Slack demo
   SLACK_SIGNING_SECRET=<from 2e>
   SLACK_CHANNEL=#opssentinel
   ```
   Leave the `localhost` URLs, the `*_changeme` Elastic/Phoenix placeholders, and `DATABASE_URL` as
   they are — the local stack provides those.
3. Double-check `.env` is git-ignored: `git status` should **not** list `.env`.

- [ ] `.env` created and filled; `.env` does not appear in `git status`

---

## 4. 🟥 One decision to make (for Task 4 of the prompt)

The spec requires the agent to use **Google ADK (Graph Workflows) + `McpToolset`**. The project
currently uses a custom orchestrator instead (it works, but it isn't literally ADK). When the agent
reaches **Task 4**, it will ask you to choose:

- **Option A — Use real Google ADK** (most faithful to the spec; more work). Choose this if this is
  an academic/spec-conformance project or you want the resume-grade "built on Google ADK" claim.
- **Option B — Keep the custom orchestrator, document the deviation, and add manual tracing**
  (faster; still meets the observability criterion). Choose this if you mainly want a working demo.

Decide which you want so you can answer quickly. **If unsure, Option A is the safer choice for a
spec-graded project.**

- [ ] I know whether I want Option A or Option B

---

## 5. 🟨 Optional: Google Cloud deployment prerequisites (only for Task 7)

Skip this for the local validation. Do it only when you want to deploy to real GCP.

1. Create a **GCP project** and **enable billing**.
2. `gcloud auth login` and `gcloud config set project <your-project-id>`.
3. Enable the APIs: Cloud Run, Pub/Sub, Cloud SQL, Secret Manager, Artifact Registry, Cloud
   Scheduler, Compute Engine, IAM.
4. Pick the real project id and region — the agent will pass them as Terraform `-var project_id=…`.
5. You'll create the **Secret Manager secret versions** (the agent provisions the empty secrets;
   you add the real values) and, for the dashboard, add your **production domain** to the OAuth
   client's authorized origins.

- [ ] (optional) GCP project ready, APIs enabled, `gcloud` authenticated

---

## You're ready — how to hand off to the agent

When boxes 0–3 (and ideally 4) are checked:

1. Open the project in **Claude Code** (or your AI agent of choice).
2. Make sure Docker Desktop is **running**.
3. Paste the entire contents of
   **`PROMPTS/06-phase6-integration-validation-and-fidelity.md`** as your message.
4. The agent will start at **Task 0 (preflight)**, then work one task at a time, stopping after each
   for you to review. Answer its **Task 4** question (Option A or B) when it asks.
5. For the Slack demo (Task 3), start your tunnel and set the Slack Request URL once the stack is up.

### Quick reference — what each secret is for
| `.env` variable | What it is | Where you got it |
|---|---|---|
| `GEMINI_API_KEY` | Gemini 2.0 Flash (agent reasoning) | 2a — AI Studio |
| `SESSION_SECRET` | signs the dashboard login cookie | 2b — `openssl rand` |
| `GOOGLE_OAUTH_CLIENT_ID` | "Sign in with Google" on the dashboard | 2d — Cloud Console |
| `SLACK_BOT_TOKEN` | lets the bot post the brief | 2e — Slack app |
| `SLACK_SIGNING_SECRET` | verifies Slack button clicks | 2e — Slack app |
| `SLACK_CHANNEL` | where briefs are posted | 2e — your Slack |
| `DATABASE_URL`, `ELASTIC_URL`, Phoenix, Pub/Sub | local services | left as-is (docker-compose) |

> If you get stuck on any step, tell the agent which step number you're on and what error you see —
> it can help you troubleshoot Docker, the tunnel, or the OAuth/Slack config.
