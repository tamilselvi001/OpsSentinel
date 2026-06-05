import { getSourceHealth } from "@/lib/data/incidents";
import type { SourceHealth } from "@/lib/types/metrics";

const statusColor: Record<SourceHealth["status"], string> = {
  healthy: "bg-green-100 text-green-700",
  degraded: "bg-amber-100 text-amber-800",
  unknown: "bg-zinc-100 text-zinc-600",
};

export default async function HealthPage() {
  const sources = await getSourceHealth();
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Operational health
        </h1>
        <p className="text-sm text-zinc-500">Connected sources and platform status.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {sources.map((source) => (
          <div
            key={source.name}
            className="rounded-lg border border-zinc-200 p-5 dark:border-zinc-800"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-zinc-900 dark:text-zinc-50">{source.name}</span>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor[source.status]}`}
              >
                {source.status}
              </span>
            </div>
            <p className="mt-2 text-sm text-zinc-500">{source.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
