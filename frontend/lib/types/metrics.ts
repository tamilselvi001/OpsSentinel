// Reliability & observability metrics — the MVP success metrics the director persona needs:
// AI decision accuracy, calibration, and overall operational health. `null` means "not available".

export interface ReliabilityMetrics {
  mttd_seconds: number | null; // mean time to detect
  mttr_minutes: number | null; // mean time to resolve (known patterns)
  triage_accuracy: number | null; // correct category/severity/team, fraction
  correlation_precision: number | null; // alert-correlation precision, fraction
  autonomous_approval_rate: number | null; // first-pass approval rate, fraction
  calibration_variance: number | null; // |stated confidence − empirical accuracy| (< 0.05 target)
  autonomy_coverage: number | null; // fraction of incidents handled at high autonomy
  open_incidents: number;
  total_incidents: number;
}

export interface SourceHealth {
  name: string;
  status: "healthy" | "degraded" | "unknown";
  detail: string;
}
