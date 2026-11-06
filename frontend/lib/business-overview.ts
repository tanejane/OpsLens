import type { DashboardData, DashboardMetric } from "../components/BusinessDashboard";

/** Null, blank and non-finite readings are unavailable, never zero. */
export function finiteReading(value: unknown): number | null {
  if ((typeof value !== "number" && typeof value !== "string") || String(value).trim() === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function isMeasured(metric?: DashboardMetric): boolean {
  return metric?.status === "MEASURED" && finiteReading(metric.current?.value) !== null && finiteReading(metric.previous?.value) !== null;
}

export function formatReading(value: unknown, digits = 2): string {
  const n = finiteReading(value);
  return n === null ? "—" : new Intl.NumberFormat("en", { maximumFractionDigits: digits }).format(n);
}

export function changeText(metric?: DashboardMetric): string {
  if (!isMeasured(metric)) return "Comparison unavailable";
  const delta = finiteReading(metric?.delta);
  if (delta === null) return "Change unavailable";
  const suffix = metric?.delta_unit === "percentage_points" ? " pp" : metric?.delta_unit === "score_points" ? " pts" : metric?.unit === "orders" ? " orders" : "";
  return `${delta > 0 ? "+" : ""}${formatReading(delta)}${suffix}`;
}

export function validDashboard(value: DashboardData, month: string): boolean {
  const validPeriod = (p: unknown) => Array.isArray(p) && p.length === 2 && p.every(x => typeof x === "string" && /^\d{4}-\d{2}-\d{2}$/.test(x) && Number.isFinite(Date.parse(x))) && p[0] < p[1];
  return !!value && value.month === month && validPeriod(value.periods?.current) && validPeriod(value.periods?.previous)
    && value.periods.current[0].slice(0, 7) === month && !!value.metrics && typeof value.metrics === "object";
}

export function replayUrl(record: Record<string, unknown>): string | null {
  const payload = record.payload as Record<string, unknown> | undefined;
  const audit = payload?.observability as { persistence?: string; run_id?: string } | undefined;
  const context = payload?.context_provenance as { session_id?: string } | undefined;
  return audit?.persistence === "SAVED" && audit.run_id && context?.session_id
    ? `/api/investigation-sessions/${encodeURIComponent(context.session_id)}/runs/${encodeURIComponent(audit.run_id)}/replay` : null;
}

export function disposition(record: Record<string, unknown>): string {
  const p = record.payload as Record<string, unknown> | undefined;
  const status = String(p?.status ?? "");
  if (status.includes("PARTIAL") || status === "INSUFFICIENT_GOVERNED_EVIDENCE") return "Partial evidence";
  if (status === "EXECUTION_FAILED") return "Unavailable";
  if (status === "NEEDS_CLARIFICATION") return "Clarification needed";
  if (status === "ACTIONABLE_EVIDENCE_GAP") return "Evidence gap";
  if (status.includes("NOT_SUPPORTED") || status.includes("NOT_YET_SUPPORTED")) return "Not supported";
  if (status === "MEASURED_WITH_LIMITATIONS" || status === "MEASURED_WITH_SCOPE_LIMITS") return "Measured · scope limits";
  if (p?.executable === true && p?.causal_claim === false) return "Descriptive evidence";
  return "Unverified";
}
