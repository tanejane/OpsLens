import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { DashboardMetric } from "./BusinessDashboard";
import { changeText, finiteReading, formatReading, isMeasured } from "../lib/business-overview";

export function OverviewPanel({ title, children, className = "", action }: { title: string; children: ReactNode; className?: string; action?: ReactNode }) {
  return <section className={`overview-panel ${className}`} aria-label={title}><header className="overview-panel-head"><h2>{title}</h2>{action}</header>{children}</section>;
}

export function MetricChange({ metric }: { metric?: DashboardMetric }) {
  const delta = isMeasured(metric) ? finiteReading(metric?.delta) : null;
  const Icon = delta !== null && delta > 0 ? ArrowUpRight : delta !== null && delta < 0 ? ArrowDownRight : Minus;
  return <span className="overview-change"><Icon size={14} aria-hidden="true" />{changeText(metric)}</span>;
}

export function ComparisonBars({ name, metric, previous, current }: { name: string; metric?: DashboardMetric; previous: string; current: string }) {
  if (!isMeasured(metric)) return <div className="overview-comparison"><h3>{name}</h3><p className="overview-muted">Comparison unavailable</p></div>;
  const before = finiteReading(metric?.previous?.value)!;
  const after = finiteReading(metric?.current?.value)!;
  const max = Math.max(Math.abs(before), Math.abs(after));
  // Each measure uses its own zero-based magnitude scale; signs remain explicit.
  return <div className="overview-comparison"><div className="overview-comparison-head"><h3>{name}</h3><MetricChange metric={metric} /></div>
    {[[previous, before], [current, after]].map(([period, raw], i) => {
      const value = raw as number;
      return <div className={`overview-bar-row ${i ? "is-current" : ""}`} key={String(period)}>
        <span>{period}</span><span className="overview-bar-track" aria-hidden="true"><i className={value < 0 ? "is-negative" : ""} style={{ width: `${max ? Math.abs(value) / max * 100 : 0}%` }} /></span><strong>{formatReading(value)}</strong>
      </div>;
    })}
    {(before < 0 || after < 0) && <small className="overview-muted">Bars show magnitude; negative values indicate losses.</small>}
  </div>;
}
