import MetricCard from "@/components/MetricCard";
import { getMetrics } from "@/lib/data/incidents";

const pct = (value: number | null): string =>
  value === null ? "—" : `${Math.round(value * 100)}%`;

export default async function ReliabilityPage() {
  const m = await getMetrics();
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Reliability &amp; observability
        </h1>
        <p className="text-sm text-zinc-500">
          AI decision accuracy, calibration, and overall operational health.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="MTTD"
          value={m.mttd_seconds === null ? "—" : `${m.mttd_seconds}s`}
          hint="target < 30s"
        />
        <MetricCard
          label="MTTR"
          value={m.mttr_minutes === null ? "—" : `${m.mttr_minutes.toFixed(1)}m`}
          hint="known patterns < 10m"
        />
        <MetricCard label="Triage accuracy" value={pct(m.triage_accuracy)} hint="target > 90%" />
        <MetricCard label="Correlation precision" value={pct(m.correlation_precision)} />
        <MetricCard
          label="Autonomous approval rate"
          value={pct(m.autonomous_approval_rate)}
          hint="target > 80%"
        />
        <MetricCard
          label="Calibration variance"
          value={pct(m.calibration_variance)}
          hint="target < 5%"
        />
        <MetricCard label="Autonomy coverage" value={pct(m.autonomy_coverage)} />
        <MetricCard label="Open incidents" value={String(m.open_incidents)} />
        <MetricCard label="Total incidents" value={String(m.total_incidents)} />
      </div>
    </section>
  );
}
