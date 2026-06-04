"""Phase-2 observability store: agent_outcomes (projection of Phoenix LLM-as-judge evaluations).

Backs the Arize MCP server's accuracy / calibration / novelty tools. Member 3's (observability)
data — additive to the Phase-1 incident store, not a change to it.

Revision ID: 0002_agent_outcomes
Revises: 0001_initial_schema
Create Date: 2026-06-02
"""

from alembic import op

revision = "0002_agent_outcomes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_outcomes (
            outcome_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            trace_id          text,
            incident_id       uuid REFERENCES incidents (incident_id) ON DELETE SET NULL,
            category          text,
            approved          boolean,
            successful        boolean,
            stated_confidence double precision,
            created_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_agent_outcomes_category ON agent_outcomes (category)")
    op.execute("CREATE INDEX idx_agent_outcomes_created_at ON agent_outcomes (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_outcomes")
