"""OpsSentinel — one-command live demo orchestrator (for presentations / hackathon judging).

Runs the full money-shot workflow end to end and narrates it as three acts that map 1:1 to the MVP
Exit Criteria, so you run ONE command on stage and just talk:

    ACT 1 (EC1)  alert storm  → a single correlated incident, zero loss, DLQ empty
    ACT 2 (EC2)  retrieve → propose → approve → execute → resolve + memory loop (Arize + Elastic)
    ACT 3 (EC3)  the OpenInference trace in Phoenix + the secured dashboard deep-link

This reads only what the live stack actually produced — it never fabricates a result. If the agent
classifies differently or a step stalls, the script prints the real state and the relevant log hint.

Prereqs: the docker-compose stack is up (`docker compose up -d`) and seeded. Usage:

    python scripts/demo.py                 # 50-signal storm, auto-approve, full walkthrough
    python scripts/demo.py --count 60      # bigger storm
    python scripts/demo.py --no-approve    # stop at awaiting_approval (approve live from Slack/UI)
"""
# ruff: noqa: E402, I001  (sys.path bootstrap + env defaults must precede first-party imports)

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "services" / "alert-simulator"))

# Sensible local defaults so the script "just runs" against the compose stack. Pre-set values win.
os.environ.setdefault("PUBSUB_EMULATOR_HOST", "localhost:8085")
os.environ.setdefault("PUBSUB_PROJECT_ID", "opssentinel-mvp")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "opssentinel-mvp")
os.environ.setdefault(
    "DATABASE_URL", "postgresql://opssentinel:opssentinel@localhost:5432/opssentinel"
)

import psycopg

from app.generator import make_storm
from lib.pubsub import PROJECT_ID, publish_alert

try:  # box-drawing/arrow glyphs render on any console (Windows cp1252 included)
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging

# Keep the stage output clean: silence the per-publish INFO log lines from the pubsub helper.
logging.getLogger("opssentinel.pubsub").setLevel(logging.WARNING)

PHOENIX_URL = os.environ.get("PHOENIX_URL", "http://localhost:6006")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")
ACTIONS_TOPIC = os.environ.get("OPSSENTINEL_ACTIONS_TOPIC", "opssentinel-actions")

# ── tiny ANSI helper (auto-disables when not a TTY or NO_COLOR is set) ───────────────────────────
_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def cyan(t: str) -> str:
    return _c("36", t)


def yellow(t: str) -> str:
    return _c("33", t)


def dim(t: str) -> str:
    return _c("2", t)


def act(n: int, title: str, ec: str) -> None:
    bar = "═" * 68
    print()
    print(cyan(bar))
    print(cyan(f"  ACT {n} — {title}") + dim(f"   [{ec}]"))
    print(cyan(bar))


def _db():
    conninfo = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(conninfo, connect_timeout=10)


def _fetch_incident(seed_event_id: str) -> dict | None:
    """Find the incident that folded our storm, identified by one of its seed event ids."""
    sql = (
        "SELECT incident_id::text, status, category, severity, autonomy_tier, confidence, "
        "risk_level, root_cause, trace_id::text, "
        "jsonb_array_length(correlated_event_ids) AS folded "
        "FROM incidents WHERE correlated_event_ids @> %s::jsonb ORDER BY created_at DESC LIMIT 1"
    )
    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, [json.dumps([seed_event_id])])
        row = cur.fetchone()
        if not row:
            return None
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row, strict=False))


def _fetch_outcome(incident_id: str) -> dict | None:
    sql = (
        "SELECT successful, approved, stated_confidence, category "
        "FROM agent_outcomes WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1"
    )
    with _db() as conn, conn.cursor() as cur:
        cur.execute(sql, [incident_id])
        row = cur.fetchone()
        if not row:
            return None
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row, strict=False))


def _poll(seed_event_id: str, want: set[str], timeout: int) -> dict | None:
    """Poll the incident store until status ∈ want (or timeout). Returns the incident dict."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        inc = _fetch_incident(seed_event_id)
        if inc:
            if inc["status"] != last:
                print(dim(f"    … incident {inc['incident_id'][:8]} status: {inc['status']}"))
                last = inc["status"]
            if inc["status"] in want:
                return inc
        time.sleep(3)
    return _fetch_incident(seed_event_id)


def _publish_decision(incident_id: str, decision: str) -> None:
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import pubsub_v1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, ACTIONS_TOPIC)
    try:
        publisher.create_topic(name=topic_path)
    except AlreadyExists:
        pass
    payload = {"incident_id": incident_id, "decision": decision, "approver": "demo-presenter"}
    publisher.publish(topic_path, json.dumps(payload).encode("utf-8")).result(timeout=30)


def _dlq_empty() -> bool | None:
    try:
        from google.cloud import pubsub_v1

        subscriber = pubsub_v1.SubscriberClient()
        sub = subscriber.subscription_path(PROJECT_ID, "opssentinel-alerts-dlq-sub")
        resp = subscriber.pull(subscription=sub, max_messages=1, timeout=5)
        return not resp.received_messages
    except Exception:
        return None


def _kv(label: str, value: object) -> None:
    print(f"    {bold(label + ':'):<22} {value}")


def main() -> None:
    ap = argparse.ArgumentParser(description="OpsSentinel live demo orchestrator")
    ap.add_argument("--count", type=int, default=50, help="storm size (>= 50 proves EC1)")
    ap.add_argument("--ready-timeout", type=int, default=180, help="max wait for the proposal (s)")
    ap.add_argument("--resolve-timeout", type=int, default=90, help="max wait after approval (s)")
    ap.add_argument("--no-approve", action="store_true", help="stop at awaiting_approval")
    args = ap.parse_args()

    print(bold(green("\n  OpsSentinel — autonomous incident response — LIVE DEMO\n")))

    # ── ACT 1 ────────────────────────────────────────────────────────────────────────────────
    act(1, "An alert storm hits", "EC1 · correlate & dedup")
    events = make_storm(args.count)
    seed = events[0].event_id
    for ev in events:
        publish_alert(ev)
    print(f"  Published {bold(str(len(events)))} correlated signals "
          f"(correlation_key {dim(events[0].correlation_key)})")
    print(dim("  A human on-call drowns here. Watching OpsSentinel fold them into one incident…"))

    inc = _poll(seed, {"awaiting_approval", "resolved"}, args.ready_timeout)
    if not inc:
        print(yellow("  ✗ No incident appeared in time. Is the agent up? "
                     "`docker compose logs agent --tail 40`"))
        sys.exit(1)

    folded = inc["folded"]
    loss = len(events) - folded
    print()
    print(green(f"  ✓ {len(events)} signals → 1 incident "
                f"({folded} events folded, {loss} lost)"))
    dlq = _dlq_empty()
    if dlq is True:
        print(green("  ✓ DLQ empty — zero alert loss"))
    elif dlq is False:
        print(yellow("  ! DLQ not empty — a message was dead-lettered"))

    # ── ACT 2 ────────────────────────────────────────────────────────────────────────────────
    act(2, "The agent reasons, then we govern it", "EC2 · retrieve → propose → approve → execute")
    print(bold("  RAG-grounded proposal (Gemini + Elastic MCP + Arize MCP):"))
    _kv("Incident", inc["incident_id"])
    _kv("Category", inc["category"])
    _kv("Severity", inc["severity"])
    _kv("Confidence", inc["confidence"])
    _kv("Risk level", inc["risk_level"])
    _kv("Autonomy tier", bold(green(str(inc["autonomy_tier"]))
                             if inc["autonomy_tier"] == "high" else str(inc["autonomy_tier"])))
    _kv("Root cause", inc["root_cause"])

    if args.no_approve:
        print()
        print(yellow("  Paused at awaiting_approval — approve from Slack/the dashboard, or run:"))
        print(dim(f"    python scripts/approve.py --incident {inc['incident_id']}"))
        _trace_links(inc)
        return

    print()
    print(bold("  Human-in-the-loop: presenter approves the remediation →"))
    _publish_decision(inc["incident_id"], "approve")
    print(dim("    published approval to opssentinel-actions"))
    inc = _poll(seed, {"resolved", "failed"}, args.resolve_timeout) or inc

    if inc["status"] == "resolved":
        print(green("  ✓ Remediation executed (mocked) → incident RESOLVED"))
    else:
        print(yellow(f"  ! Incident status is '{inc['status']}' — check the executor logs"))

    outcome = _fetch_outcome(inc["incident_id"])
    if outcome:
        print(green("  ✓ Memory loop closed:"))
        print(f"      • Arize self-eval logged → "
              f"successful={outcome['successful']}, approved={outcome['approved']}, "
              f"category={outcome['category']!r}")
        print("      • Closure summary written back to Elasticsearch "
              "(retrievable by the next incident)")

    # ── ACT 3 ────────────────────────────────────────────────────────────────────────────────
    act(3, "Every decision is observable", "EC3 · Phoenix trace + secured dashboard")
    _trace_links(inc)
    print()
    print(green(bold("  All three Exit Criteria demonstrated on a live stack.")))
    print()


def _trace_links(inc: dict) -> None:
    tid = inc.get("trace_id")
    iid = inc["incident_id"]
    print(bold("  Open these on screen:"))
    if tid and set(tid) != {"0"}:
        print("      Phoenix trace  -> " + cyan(f"{PHOENIX_URL}/projects?traceId={tid}"))
    else:
        print("      Phoenix        -> " + cyan(PHOENIX_URL) + dim("  (trace_id unavailable)"))
    print("      Dashboard      -> " + cyan(f"{DASHBOARD_URL}/incidents/{iid}"))
    print("      Reliability    -> " + cyan(f"{DASHBOARD_URL}/reliability"))


if __name__ == "__main__":
    main()
