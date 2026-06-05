import Link from "next/link";

import IncidentTable from "@/components/IncidentTable";
import { listIncidents } from "@/lib/data/incidents";
import type {
  IncidentFilters,
  IncidentStatus,
  Severity,
} from "@/lib/types/incident";

const STATUSES: IncidentStatus[] = [
  "open",
  "awaiting_approval",
  "executing",
  "resolved",
  "escalated",
];
const SEVERITIES: Severity[] = ["P1", "P2", "P3", "P4"];

function FilterLink({
  active,
  href,
  children,
}: {
  active: boolean;
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`rounded-full border px-3 py-1 text-xs ${
        active
          ? "border-blue-600 bg-blue-600 text-white"
          : "border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300"
      }`}
    >
      {children}
    </Link>
  );
}

export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; severity?: string }>;
}) {
  const sp = await searchParams;
  const filters: IncidentFilters = {
    status: STATUSES.includes(sp.status as IncidentStatus)
      ? (sp.status as IncidentStatus)
      : undefined,
    severity: SEVERITIES.includes(sp.severity as Severity)
      ? (sp.severity as Severity)
      : undefined,
  };
  const incidents = await listIncidents(filters);

  const withParam = (key: "status" | "severity", value?: string) => {
    const next = new URLSearchParams();
    if (filters.status && !(key === "status")) next.set("status", filters.status);
    if (filters.severity && !(key === "severity")) next.set("severity", filters.severity);
    if (value) next.set(key, value);
    const qs = next.toString();
    return qs ? `/incidents?${qs}` : "/incidents";
  };

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Incidents</h1>
        <p className="text-sm text-zinc-500">
          Current incident state produced by the agent. Read-only.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-zinc-400">Status:</span>
        <FilterLink active={!filters.status} href={withParam("status")}>
          all
        </FilterLink>
        {STATUSES.map((status) => (
          <FilterLink
            key={status}
            active={filters.status === status}
            href={withParam("status", status)}
          >
            {status.replace(/_/g, " ")}
          </FilterLink>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-zinc-400">Severity:</span>
        <FilterLink active={!filters.severity} href={withParam("severity")}>
          all
        </FilterLink>
        {SEVERITIES.map((severity) => (
          <FilterLink
            key={severity}
            active={filters.severity === severity}
            href={withParam("severity", severity)}
          >
            {severity}
          </FilterLink>
        ))}
      </div>

      <IncidentTable incidents={incidents} />
    </section>
  );
}
