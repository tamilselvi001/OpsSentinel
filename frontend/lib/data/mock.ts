// Typed mock of the incident read-model + metrics, so the UI and auth can be built and demoed
// without a live agent (OPSSENTINEL_DATA_MODE=mock).

import type {
  AuditEntry,
  IncidentDetail,
  IncidentFilters,
  IncidentSummary,
} from "@/lib/types/incident";
import type { ReliabilityMetrics, SourceHealth } from "@/lib/types/metrics";

const NOW = Date.now();
const iso = (minutesAgo: number) => new Date(NOW - minutesAgo * 60_000).toISOString();

const DETAILS: IncidentDetail[] = [
  {
    incident_id: "11111111-1111-1111-1111-111111111111",
    status: "awaiting_approval",
    severity: "P1",
    category: "Database Connection Pool",
    title: "[P1] Database Connection Pool on payment-service",
    confidence: 0.88,
    risk_level: "high",
    autonomy_tier: "moderate",
    created_at: iso(8),
    updated_at: iso(2),
    root_cause: "Connection pool exhausted after the 00:00 deploy; new queries time out.",
    correlated_event_ids: ["evt-1", "evt-2", "evt-3", "evt-4"],
    recommended_action: {
      steps: ["Restart the connection pool", "Raise max pool size / DB max_connections"],
      commands: ["kubectl rollout restart deploy/payment-service -n payments-ns"],
    },
    historical_match_ids: ["rb-db-conn-limit"],
    trace_id: "abc123def456abc123def456abc12345",
    approver_subject: null,
    approval_status: null,
    approved_at: null,
    resolution_summary: null,
  },
  {
    incident_id: "22222222-2222-2222-2222-222222222222",
    status: "resolved",
    severity: "P2",
    category: "Kubernetes Pod Failure",
    title: "[P2] Kubernetes Pod Failure on checkout-service",
    confidence: 0.91,
    risk_level: "medium",
    autonomy_tier: "high",
    created_at: iso(120),
    updated_at: iso(108),
    root_cause: "CrashLoopBackOff from a failing readiness probe after rollout.",
    correlated_event_ids: ["evt-9", "evt-10"],
    recommended_action: {
      steps: ["Roll back the deployment", "Fix the probe and redeploy"],
      commands: ["kubectl rollout undo deploy/checkout-service -n checkout-ns"],
    },
    historical_match_ids: ["rb-pod-crashloop"],
    trace_id: "feed00112233feed00112233feed0011",
    approver_subject: "sub-123",
    approval_status: "approved",
    approved_at: iso(110),
    resolution_summary: "Rolled back to the previous image; error rate recovered.",
  },
  {
    incident_id: "33333333-3333-3333-3333-333333333333",
    status: "escalated",
    severity: "P1",
    category: "Network Partition",
    title: "[P1] Network Partition on payment-service",
    confidence: 0.62,
    risk_level: "high",
    autonomy_tier: "low",
    created_at: iso(45),
    updated_at: iso(20),
    root_cause: "Transient network split isolated the service from its datastore.",
    correlated_event_ids: ["evt-20", "evt-21", "evt-22"],
    recommended_action: {
      steps: ["Fail over to the standby region", "Drain the affected node"],
      commands: ["kubectl drain node-7 --ignore-daemonsets"],
    },
    historical_match_ids: ["rb-net-partition"],
    trace_id: "0bad0bad0bad0bad0bad0bad0bad0bad",
    approver_subject: null,
    approval_status: null,
    approved_at: null,
    resolution_summary: null,
  },
];

const AUDIT: Record<string, AuditEntry[]> = {
  "11111111-1111-1111-1111-111111111111": [
    {
      audit_id: "a1",
      actor: "agent",
      action: "transition:correlating",
      details: { events: 4 },
      created_at: iso(8),
    },
    {
      audit_id: "a2",
      actor: "agent",
      action: "transition:awaiting_approval",
      details: { autonomy_tier: "moderate", risk_level: "high" },
      created_at: iso(2),
    },
  ],
};

const toSummary = (d: IncidentDetail): IncidentSummary => ({
  incident_id: d.incident_id,
  status: d.status,
  severity: d.severity,
  category: d.category,
  title: d.title,
  confidence: d.confidence,
  risk_level: d.risk_level,
  autonomy_tier: d.autonomy_tier,
  created_at: d.created_at,
  updated_at: d.updated_at,
});

export function filterIncidents(filters: IncidentFilters): IncidentSummary[] {
  return DETAILS.filter(
    (d) =>
      (!filters.status || d.status === filters.status) &&
      (!filters.severity || d.severity === filters.severity),
  ).map(toSummary);
}

export function findIncident(id: string): IncidentDetail | null {
  return DETAILS.find((d) => d.incident_id === id) ?? null;
}

export function auditFor(id: string): AuditEntry[] {
  return AUDIT[id] ?? [];
}

export function metrics(): ReliabilityMetrics {
  return {
    mttd_seconds: 22,
    mttr_minutes: 8.5,
    triage_accuracy: 0.92,
    correlation_precision: 0.96,
    autonomous_approval_rate: 0.83,
    calibration_variance: 0.03,
    autonomy_coverage: 0.61,
    open_incidents: DETAILS.filter((d) => !["resolved", "rejected"].includes(d.status)).length,
    total_incidents: DETAILS.length,
  };
}

export function sources(): SourceHealth[] {
  return [
    { name: "Pub/Sub queue", status: "healthy", detail: "ingesting normalized alerts" },
    { name: "Elastic MCP", status: "healthy", detail: "semantic memory online" },
    { name: "Arize Phoenix MCP", status: "healthy", detail: "self-evaluation online" },
    { name: "Incident store", status: "healthy", detail: "PostgreSQL HA" },
  ];
}
