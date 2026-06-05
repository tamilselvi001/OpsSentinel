import Link from "next/link";
import { notFound } from "next/navigation";

import { AutonomyBadge, RiskBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import { getPhoenixBaseUrl } from "@/lib/config";
import { getAuditTrail, getIncident } from "@/lib/data/incidents";

function phoenixTraceUrl(traceId: string): string {
  // Best-effort deep link into the Phoenix UI keyed on the trace id (route is configurable).
  return `${getPhoenixBaseUrl().replace(/\/$/, "")}/projects?traceId=${traceId}`;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">{title}</h2>
      {children}
    </div>
  );
}

export default async function IncidentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const incident = await getIncident(id);
  if (!incident) {
    notFound();
  }
  const audit = await getAuditTrail(id);

  return (
    <article className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <SeverityBadge severity={incident.severity} />
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          {incident.title ?? incident.category ?? incident.incident_id}
        </h1>
        <StatusBadge status={incident.status} />
      </div>

      <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-zinc-500">
        <span>Team: {incident.category ?? "—"}</span>
        <span>
          Confidence:{" "}
          {incident.confidence === null ? "—" : `${Math.round(incident.confidence * 100)}%`}
        </span>
        <span className="flex items-center gap-1">
          Autonomy: <AutonomyBadge tier={incident.autonomy_tier} />
        </span>
        <span className="flex items-center gap-1">
          Risk: <RiskBadge risk={incident.risk_level} />
        </span>
      </div>

      <Section title="Root cause">
        <p className="text-sm text-zinc-700 dark:text-zinc-300">{incident.root_cause ?? "—"}</p>
      </Section>

      <Section title="Proposed remediation">
        {incident.recommended_action ? (
          <>
            <ol className="list-decimal space-y-1 pl-5 text-sm text-zinc-700 dark:text-zinc-300">
              {incident.recommended_action.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
            {incident.recommended_action.commands.length > 0 && (
              <pre className="mt-3 overflow-x-auto rounded bg-zinc-900 p-3 text-xs text-zinc-100">
                {incident.recommended_action.commands.join("\n")}
              </pre>
            )}
          </>
        ) : (
          <p className="text-sm text-zinc-400">No recommendation yet.</p>
        )}
      </Section>

      <div className="grid gap-6 md:grid-cols-2">
        <Section title="Correlated evidence">
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            {incident.correlated_event_ids.length} correlated signals
          </p>
        </Section>
        <Section title="Historical precedent">
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            {incident.historical_match_ids.length > 0
              ? incident.historical_match_ids.join(", ")
              : "—"}
          </p>
        </Section>
      </div>

      {incident.resolution_summary && (
        <Section title="Resolution">
          <p className="text-sm text-zinc-700 dark:text-zinc-300">{incident.resolution_summary}</p>
        </Section>
      )}

      <Section title="Observability">
        {incident.trace_id ? (
          <a
            href={phoenixTraceUrl(incident.trace_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            Open Arize Phoenix trace ({incident.trace_id.slice(0, 12)}…)
          </a>
        ) : (
          <p className="text-sm text-zinc-400">No trace recorded.</p>
        )}
      </Section>

      <Section title="Audit timeline">
        {audit.length === 0 ? (
          <p className="text-sm text-zinc-400">No audit entries.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {audit.map((entry) => (
              <li key={entry.audit_id} className="flex flex-wrap gap-2 text-zinc-600 dark:text-zinc-300">
                <span className="text-zinc-400">{new Date(entry.created_at).toLocaleString()}</span>
                <span className="font-medium">{entry.actor}</span>
                <span>{entry.action}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Link href="/incidents" className="inline-block text-sm text-blue-600 hover:underline">
        ← Back to incidents
      </Link>
    </article>
  );
}
