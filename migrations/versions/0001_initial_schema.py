"""Initial incident-store schema: enums, 4 core tables, indexes, SLA seed rows.

Implements the Phase-1 Section-3 contract exactly. Note: the master-index contract also
defines a `blast_radius` column on `incidents`; it is intentionally omitted here to match the
Phase-1 spec, and can be added in a follow-up migration when Phase 3 needs it.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-01
"""

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE incident_status AS ENUM ("
        "'open','correlating','analyzing','awaiting_approval','approved',"
        "'executing','resolved','rejected','escalated')"
    )
    op.execute("CREATE TYPE incident_severity AS ENUM ('P1','P2','P3','P4')")
    op.execute("CREATE TYPE risk_level AS ENUM ('low','medium','high')")
    op.execute("CREATE TYPE autonomy_tier AS ENUM ('high','moderate','low')")

    # ── incidents ────────────────────────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE incidents (
            incident_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            status               incident_status   NOT NULL DEFAULT 'open',
            severity             incident_severity,
            category             text,
            title                text,
            root_cause           text,
            confidence           double precision,
            risk_level           risk_level,
            correlated_event_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
            recommended_action   jsonb,
            historical_match_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
            autonomy_tier        autonomy_tier,
            trace_id             text,
            approver_subject     text,
            approval_status      text,
            approved_at          timestamptz,
            resolution_summary   text,
            created_at           timestamptz NOT NULL DEFAULT now(),
            updated_at           timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_incidents_status ON incidents (status)")
    op.execute("CREATE INDEX idx_incidents_severity ON incidents (severity)")
    op.execute("CREATE INDEX idx_incidents_created_at ON incidents (created_at)")

    # ── incident_events (raw correlated events; carries correlation_key) ──────
    op.execute(
        """
        CREATE TABLE incident_events (
            event_pk        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            incident_id     uuid REFERENCES incidents (incident_id) ON DELETE CASCADE,
            correlation_key text,
            event           jsonb NOT NULL,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_incident_events_incident_id ON incident_events (incident_id)")
    op.execute(
        "CREATE INDEX idx_incident_events_correlation_key ON incident_events (correlation_key)"
    )

    # ── audit_log (append-only; every AI decision + human action) ────────────
    op.execute(
        """
        CREATE TABLE audit_log (
            audit_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            incident_id uuid REFERENCES incidents (incident_id) ON DELETE SET NULL,
            actor       text NOT NULL,
            action      text NOT NULL,
            details     jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_audit_log_incident_id ON audit_log (incident_id)")
    op.execute("CREATE INDEX idx_audit_log_created_at ON audit_log (created_at)")

    # ── sla_policies (per-severity response/resolution windows) ──────────────
    op.execute(
        """
        CREATE TABLE sla_policies (
            severity               incident_severity PRIMARY KEY,
            respond_within_minutes integer NOT NULL,
            resolve_within_minutes integer NOT NULL,
            created_at             timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    # Governance defaults: spec fixes P1 respond <= 15 min, P2 <= 60 min; resolution windows
    # are reasonable defaults derived from the severity tiers (documented assumption).
    op.execute(
        """
        INSERT INTO sla_policies (severity, respond_within_minutes, resolve_within_minutes) VALUES
            ('P1', 15, 60),
            ('P2', 60, 240),
            ('P3', 240, 1440),
            ('P4', 1440, 5760)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sla_policies")
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS incident_events")
    op.execute("DROP TABLE IF EXISTS incidents")
    op.execute("DROP TYPE IF EXISTS autonomy_tier")
    op.execute("DROP TYPE IF EXISTS risk_level")
    op.execute("DROP TYPE IF EXISTS incident_severity")
    op.execute("DROP TYPE IF EXISTS incident_status")
