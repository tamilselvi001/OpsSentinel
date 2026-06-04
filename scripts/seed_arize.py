"""Seed the Arize observability store (agent_outcomes) with synthetic evaluation history.

Idempotent: clears prior synthetic rows (those with null incident_id) before inserting. Run via
`make seed`. Requires migration 0002 applied.
"""
# ruff: noqa: E402, I001  (sys.path bootstrap must precede first-party imports)

from __future__ import annotations

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import seed_data
from sqlalchemy import text

from lib.db import transaction


def main() -> None:
    outcomes = seed_data.arize_outcomes()
    insert = text(
        "INSERT INTO agent_outcomes (category, approved, successful, stated_confidence) "
        "VALUES (:category, :approved, :successful, :stated_confidence)"
    )
    with transaction() as conn:
        # Idempotent reseed: remove prior synthetic rows (synthetic rows have no incident link).
        conn.execute(text("DELETE FROM agent_outcomes WHERE incident_id IS NULL"))
        conn.execute(insert, outcomes)
    n_categories = len(seed_data.ARIZE_CATEGORY_STATS)
    print(f"seeded {len(outcomes)} arize outcomes across {n_categories} categories")


if __name__ == "__main__":
    main()
