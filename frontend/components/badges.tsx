import type {
  AutonomyTier,
  IncidentStatus,
  RiskLevel,
  Severity,
} from "@/lib/types/incident";

const pill = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
const dash = <span className="text-zinc-400">—</span>;

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) return dash;
  const colors: Record<Severity, string> = {
    P1: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
    P2: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
    P3: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
    P4: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  };
  return <span className={`${pill} ${colors[severity]}`}>{severity}</span>;
}

export function StatusBadge({ status }: { status: IncidentStatus }) {
  const colors: Record<IncidentStatus, string> = {
    open: "bg-zinc-100 text-zinc-700",
    correlating: "bg-blue-100 text-blue-700",
    analyzing: "bg-blue-100 text-blue-700",
    awaiting_approval: "bg-yellow-100 text-yellow-800",
    approved: "bg-green-100 text-green-700",
    executing: "bg-indigo-100 text-indigo-700",
    resolved: "bg-green-100 text-green-700",
    rejected: "bg-zinc-200 text-zinc-700",
    escalated: "bg-red-100 text-red-800",
  };
  return <span className={`${pill} ${colors[status]}`}>{status.replace(/_/g, " ")}</span>;
}

export function RiskBadge({ risk }: { risk: RiskLevel | null }) {
  if (!risk) return dash;
  const colors: Record<RiskLevel, string> = {
    low: "bg-green-100 text-green-700",
    medium: "bg-amber-100 text-amber-800",
    high: "bg-red-100 text-red-800",
  };
  return <span className={`${pill} ${colors[risk]}`}>{risk}</span>;
}

export function AutonomyBadge({ tier }: { tier: AutonomyTier | null }) {
  if (!tier) return dash;
  const colors: Record<AutonomyTier, string> = {
    high: "bg-green-100 text-green-700",
    moderate: "bg-amber-100 text-amber-800",
    low: "bg-red-100 text-red-800",
  };
  return <span className={`${pill} ${colors[tier]}`}>{tier}</span>;
}
