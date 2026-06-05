// Read-only data access for the dashboard. mock mode returns the typed mock; live mode reads the
// Phase-1 PostgreSQL incident store populated by the Phase-3 agent. Server-only (never bundled to
// the client). Reads only — the dashboard never mutates incident state.

import "server-only";

import { Pool } from "pg";

import { getDatabaseUrl, getDataMode } from "@/lib/config";
import * as mock from "@/lib/data/mock";
import type {
  AuditEntry,
  IncidentDetail,
  IncidentFilters,
  IncidentSummary,
} from "@/lib/types/incident";
import type { ReliabilityMetrics, SourceHealth } from "@/lib/types/metrics";

let pool: Pool | null = null;

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({ connectionString: getDatabaseUrl(), max: 5 });
  }
  return pool;
}

const asIso = (value: unknown): string =>
  value instanceof Date ? value.toISOString() : String(value ?? "");

const asNum = (value: unknown): number | null =>
  value === null || value === undefined ? null : Number(value);

function rowToSummary(row: Record<string, unknown>): IncidentSummary {
  return {
    incident_id: String(row.incident_id),
    status: row.status as IncidentSummary["status"],
    severity: (row.severity ?? null) as IncidentSummary["severity"],
    category: (row.category ?? null) as string | null,
    title: (row.title ?? null) as string | null,
    confidence: asNum(row.confidence),
    risk_level: (row.risk_level ?? null) as IncidentSummary["risk_level"],
    autonomy_tier: (row.autonomy_tier ?? null) as IncidentSummary["autonomy_tier"],
    created_at: asIso(row.created_at),
    updated_at: asIso(row.updated_at),
  };
}

export async function listIncidents(filters: IncidentFilters = {}): Promise<IncidentSummary[]> {
  if (getDataMode() === "mock") return mock.filterIncidents(filters);

  const clauses: string[] = [];
  const params: unknown[] = [];
  if (filters.status) {
    params.push(filters.status);
    clauses.push(`status = $${params.length}`);
  }
  if (filters.severity) {
    params.push(filters.severity);
    clauses.push(`severity = $${params.length}`);
  }
  const where = clauses.length ? `WHERE ${clauses.join(" AND ")}` : "";
  const { rows } = await getPool().query(
    `SELECT incident_id, status, severity, category, title, confidence, risk_level,
            autonomy_tier, created_at, updated_at
     FROM incidents ${where} ORDER BY created_at DESC LIMIT 200`,
    params,
  );
  return rows.map(rowToSummary);
}

export async function getIncident(id: string): Promise<IncidentDetail | null> {
  if (getDataMode() === "mock") return mock.findIncident(id);

  const { rows } = await getPool().query(`SELECT * FROM incidents WHERE incident_id = $1`, [id]);
  if (rows.length === 0) return null;
  const row = rows[0] as Record<string, unknown>;
  return {
    ...rowToSummary(row),
    root_cause: (row.root_cause ?? null) as string | null,
    correlated_event_ids: (row.correlated_event_ids ?? []) as string[],
    recommended_action: (row.recommended_action ?? null) as IncidentDetail["recommended_action"],
    historical_match_ids: (row.historical_match_ids ?? []) as string[],
    trace_id: (row.trace_id ?? null) as string | null,
    approver_subject: (row.approver_subject ?? null) as string | null,
    approval_status: (row.approval_status ?? null) as string | null,
    approved_at: row.approved_at ? asIso(row.approved_at) : null,
    resolution_summary: (row.resolution_summary ?? null) as string | null,
  };
}

export async function getAuditTrail(id: string): Promise<AuditEntry[]> {
  if (getDataMode() === "mock") return mock.auditFor(id);

  const { rows } = await getPool().query(
    `SELECT audit_id, actor, action, details, created_at
     FROM audit_log WHERE incident_id = $1 ORDER BY created_at ASC`,
    [id],
  );
  return rows.map((row: Record<string, unknown>) => ({
    audit_id: String(row.audit_id),
    actor: String(row.actor),
    action: String(row.action),
    details: (row.details ?? {}) as Record<string, unknown>,
    created_at: asIso(row.created_at),
  }));
}

export async function getMetrics(): Promise<ReliabilityMetrics> {
  if (getDataMode() === "mock") return mock.metrics();

  const pg = getPool();
  const totals = await pg.query(
    `SELECT count(*)::int AS total,
            count(*) FILTER (WHERE status NOT IN ('resolved','rejected'))::int AS open,
            avg(EXTRACT(EPOCH FROM (updated_at - created_at)) / 60.0)
              FILTER (WHERE status = 'resolved') AS mttr_minutes,
            avg(CASE WHEN autonomy_tier = 'high' THEN 1.0 ELSE 0.0 END) AS autonomy_coverage,
            avg(CASE WHEN approval_status = 'approved' THEN 1.0 ELSE 0.0 END)
              FILTER (WHERE approval_status IS NOT NULL) AS approval_rate
     FROM incidents`,
  );
  const t = totals.rows[0] as Record<string, unknown>;

  let triageAccuracy: number | null = null;
  let calibrationVariance: number | null = null;
  try {
    const evals = await pg.query(
      `SELECT avg(CASE WHEN successful THEN 1.0 ELSE 0.0 END) AS accuracy,
              abs(avg(stated_confidence) - avg(CASE WHEN successful THEN 1.0 ELSE 0.0 END)) AS calibration
       FROM agent_outcomes`,
    );
    triageAccuracy = asNum(evals.rows[0]?.accuracy);
    calibrationVariance = asNum(evals.rows[0]?.calibration);
  } catch {
    // agent_outcomes may be empty / unavailable; leave metrics null.
  }

  return {
    mttd_seconds: null, // not directly derivable from the store
    mttr_minutes: asNum(t.mttr_minutes),
    triage_accuracy: triageAccuracy,
    correlation_precision: null,
    autonomous_approval_rate: asNum(t.approval_rate),
    calibration_variance: calibrationVariance,
    autonomy_coverage: asNum(t.autonomy_coverage),
    open_incidents: (t.open as number) ?? 0,
    total_incidents: (t.total as number) ?? 0,
  };
}

export async function getSourceHealth(): Promise<SourceHealth[]> {
  return mock.sources();
}
