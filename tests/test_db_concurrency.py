"""Concurrent-update consistency test for the incident store (Phase 1, Task 5.4 acceptance).

Skips automatically when SQLAlchemy or a reachable PostgreSQL is not available (e.g. CI without
the local harness up). Run it against the docker-compose Postgres via `make test` after
`make migrate`.
"""

import concurrent.futures
import uuid

import pytest

pytest.importorskip("sqlalchemy")

from lib import db  # noqa: E402


@pytest.fixture(scope="module")
def engine_or_skip():
    try:
        engine = db.get_engine()
        with engine.connect():
            pass
    except Exception as exc:  # no DATABASE_URL or DB unreachable -> skip, don't fail
        pytest.skip(f"PostgreSQL not available: {exc}")
    return engine


def test_concurrent_upserts_keep_one_consistent_row(engine_or_skip):
    incident_id = str(uuid.uuid4())
    db.upsert_incident({"incident_id": incident_id, "status": "open", "title": "race"})

    statuses = ["correlating", "analyzing", "awaiting_approval", "approved", "executing"]

    def writer(status: str) -> None:
        db.upsert_incident({"incident_id": incident_id, "status": status})

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(statuses)) as pool:
        list(pool.map(writer, statuses))

    with engine_or_skip.connect() as conn:
        from sqlalchemy import text

        count = conn.execute(
            text("SELECT count(*) FROM incidents WHERE incident_id = :id"),
            {"id": incident_id},
        ).scalar_one()

    # Exactly one row survived the race (no duplicate / no lost insert).
    assert count == 1
    final = db.get_incident(incident_id)
    assert final is not None
    assert str(final["status"]) in statuses
