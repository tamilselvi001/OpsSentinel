"""Seed a demo incident into the incident store (optional dev convenience).

Requires the DB migrated (``make migrate``). Uses lib.db, which resolves DATABASE_URL via
lib.secrets. Run via ``make seed``.
"""

# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import uuid

from lib.db import append_audit, upsert_incident


def main() -> None:
    incident_id = str(uuid.uuid4())
    upsert_incident(
        {
            "incident_id": incident_id,
            "status": "awaiting_approval",
            "severity": "P1",
            "category": "kubernetes",
            "title": "payment-service DB connection timeouts",
            "root_cause": "primary connection pool exhausted after the 00:00 deploy",
            "confidence": 0.82,
            "risk_level": "high",
            "autonomy_tier": "moderate",
            "correlated_event_ids": ["evt-1", "evt-2", "evt-3"],
            "recommended_action": {"steps": ["restart connection pool", "scale replicas +2"]},
            "historical_match_ids": ["inc-2025-11-03"],
        }
    )
    append_audit(
        actor="seed-script",
        action="created_demo_incident",
        incident_id=incident_id,
        details={"source": "scripts/seed.py"},
    )
    print(f"seeded incident {incident_id}")


if __name__ == "__main__":
    main()
