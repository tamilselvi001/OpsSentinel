"""Shared Python helpers produced by Phase 1 and imported by every later layer.

Modules:
    events   — the normalized alert event model + correlation-key derivation
    secrets  — runtime credential accessor (Secret Manager on GCP, .env locally)
    logging  — structured JSON logging
    pubsub   — Pub/Sub publisher + bounded pull-subscriber helpers (Task 5.2)
    db       — PostgreSQL connection pool + ACID-safe data access (Task 5.4)
"""
