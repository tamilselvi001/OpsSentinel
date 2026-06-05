# OpsSentinel — developer entrypoints.
# Override PY to point at your virtualenv interpreter:
#   make test PY=.venv/Scripts/python   (Windows)
#   make test PY=.venv/bin/python       (macOS / Linux)
PY ?= python
COMPOSE ?= docker compose

.PHONY: dev down migrate seed seed-demo publish-test signal storm validate-phase2 validate approve reject build fmt lint test help

# Bring up the local stack (emulator + Postgres + Elasticsearch + Phoenix + MCP servers + sim).
dev:
	$(COMPOSE) up -d --build

# Tear the local stack down.
down:
	$(COMPOSE) down

# Apply database migrations (incident store + agent_outcomes).
migrate:
	$(PY) -m alembic upgrade head

# Seed the Phase-2 synthetic telemetry (knowledge runbooks, logs, Arize history).
seed:
	$(PY) scripts/seed_knowledge.py
	$(PY) scripts/seed_logs.py
	$(PY) scripts/seed_arize.py

# Seed a demo incident into the incident store.
seed-demo:
	$(PY) scripts/seed.py

# Publish a sample alert to the emulator and read it back.
publish-test:
	PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) scripts/publish_test.py

# Emit one mock incident signal to the queue.
signal:
	PYTHONPATH=.:services/alert-simulator PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) -m app.main signal

# Emit a 50+ signal correlated alert storm to the queue.
storm:
	PYTHONPATH=.:services/alert-simulator PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) -m app.main storm --count 50

# Validate Phase-2 semantic search + observability tools against the seeded data.
validate-phase2:
	$(PY) scripts/validate_phase2.py

# Phase-5 Exit-Criteria validation: publish a 50+ alert storm, reconcile, assert the DLQ is empty.
validate:
	PYTHONPATH=.:services/alert-simulator PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) scripts/run_storm.py

# Approve an incident (test shim for Phase-5 Slack approval). Usage: make approve INCIDENT=<id>
approve:
	PYTHONPATH=. PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) scripts/approve.py --incident $(INCIDENT)

# Reject an incident. Usage: make reject INCIDENT=<id>
reject:
	PYTHONPATH=. PUBSUB_EMULATOR_HOST=localhost:8085 $(PY) scripts/approve.py --incident $(INCIDENT) --reject

# Build the webhook-receiver container (build context = repo root).
build:
	docker build -f services/webhook-receiver/Dockerfile -t webhook-receiver .

# Format the codebase.
fmt:
	$(PY) -m ruff format .

# Lint the codebase.
lint:
	$(PY) -m ruff check .

# Run the test suite.
test:
	$(PY) -m pytest

help:
	@echo "targets: dev down migrate seed seed-demo publish-test signal storm validate-phase2 build fmt lint test"
