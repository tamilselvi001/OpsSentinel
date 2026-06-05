// Incident read-model — mirrors the Phase-1 `incidents` / `audit_log` schema. Read-only:
// the dashboard never mutates incident state (approval/execution is the Slack/agent path).

export type IncidentStatus =
  | "open"
  | "correlating"
  | "analyzing"
  | "awaiting_approval"
  | "approved"
  | "executing"
  | "resolved"
  | "rejected"
  | "escalated";

export type Severity = "P1" | "P2" | "P3" | "P4";
export type RiskLevel = "low" | "medium" | "high";
export type AutonomyTier = "high" | "moderate" | "low";

export interface RecommendedAction {
  steps: string[];
  commands: string[];
}

export interface IncidentSummary {
  incident_id: string;
  status: IncidentStatus;
  severity: Severity | null;
  category: string | null;
  title: string | null;
  confidence: number | null;
  risk_level: RiskLevel | null;
  autonomy_tier: AutonomyTier | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends IncidentSummary {
  root_cause: string | null;
  correlated_event_ids: string[];
  recommended_action: RecommendedAction | null;
  historical_match_ids: string[];
  trace_id: string | null;
  approver_subject: string | null;
  approval_status: string | null;
  approved_at: string | null;
  resolution_summary: string | null;
}

export interface AuditEntry {
  audit_id: string;
  actor: string;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface IncidentFilters {
  status?: IncidentStatus;
  severity?: Severity;
}
