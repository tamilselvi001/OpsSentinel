import Link from "next/link";

import { AutonomyBadge, RiskBadge, SeverityBadge, StatusBadge } from "@/components/badges";
import type { IncidentSummary } from "@/lib/types/incident";

function ageMinutes(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return hours < 24 ? `${hours}h` : `${Math.floor(hours / 24)}d`;
}

export default function IncidentTable({ incidents }: { incidents: IncidentSummary[] }) {
  if (incidents.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500 dark:border-zinc-700">
        No incidents match the current filters.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-4 py-3">Severity</th>
            <th className="px-4 py-3">Incident</th>
            <th className="px-4 py-3">Team</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Confidence</th>
            <th className="px-4 py-3">Autonomy</th>
            <th className="px-4 py-3">Risk</th>
            <th className="px-4 py-3">Age</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {incidents.map((incident) => (
            <tr key={incident.incident_id} className="hover:bg-zinc-50 dark:hover:bg-zinc-900">
              <td className="px-4 py-3">
                <SeverityBadge severity={incident.severity} />
              </td>
              <td className="px-4 py-3">
                <Link
                  href={`/incidents/${incident.incident_id}`}
                  className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                >
                  {incident.title ?? incident.category ?? incident.incident_id}
                </Link>
              </td>
              <td className="px-4 py-3 text-zinc-500">{incident.category ?? "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={incident.status} />
              </td>
              <td className="px-4 py-3 text-zinc-600 dark:text-zinc-300">
                {incident.confidence === null ? "—" : `${Math.round(incident.confidence * 100)}%`}
              </td>
              <td className="px-4 py-3">
                <AutonomyBadge tier={incident.autonomy_tier} />
              </td>
              <td className="px-4 py-3">
                <RiskBadge risk={incident.risk_level} />
              </td>
              <td className="px-4 py-3 text-zinc-500">{ageMinutes(incident.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
