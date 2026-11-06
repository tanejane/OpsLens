"use client";

import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleHelp, LoaderCircle } from "lucide-react";
import { dashboardInvestigationQuestion, dashboardPeriodLabel } from "../lib/dashboard";
import { requestJson } from "../lib/api-client";
import { PageHeading, SectionHeading } from "./ui";

type Reading = { value: string | number; period: string[]; source?: string; population?: Record<string, unknown>; policy?: string; time_basis?: string; limitations?: string[] };
export type DashboardMetric = { status: "MEASURED" | "UNAVAILABLE"; label?: string; definition?: string; formula?: string; source?: string; unit?: string; delta?: string; delta_unit?: string; direction?: string; current?: Reading; previous?: Reading; eligibility?: { previous?: Record<string, unknown>; current?: Record<string, unknown> }; population_note?: string; policy?: string; limitations?: string[]; reason?: string };
type Movement = { rule_id: string; title: string; metric_ids: string[]; disposition: string; causal_claim: false; validated_incident: false };
export type DashboardData = { status: string; month: string; periods: { previous: string[]; current: string[] }; metrics: Record<string, DashboardMetric>; noteworthy_movements: Movement[]; movement_rules: { rule_id: string; definition: string }[]; limitations: string[] };
type DashboardMode = "Business" | "Analyst";
const IDS = ["revenue", "contribution_profit", "orders", "contribution_margin_pct", "late_delivery_rate", "average_review_score"];
const title = (s: string) => s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const labelUnit = (unit?: string) => unit === "percent" ? "%" : unit === "score_1_to_5" ? " / 5" : unit === "dataset_currency" ? "" : unit ? ` ${unit}` : "";
const number = (v: unknown) => { const n = Number(v); return Number.isFinite(n) ? new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(n) : "—"; };
const populationSummary = (value?: Record<string, unknown>) => Object.entries(value ?? {}).map(([key, count]) => `${title(key)} ${number(count)}`).join(" · ") || "Eligibility counts were not included with this reading.";

export function BusinessDashboard({ mode, onInvestigate }: { mode: DashboardMode; onInvestigate: (question: string) => void }) {
  const [month, setMonth] = useState("2018-06");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError("");
    requestJson<DashboardData>(`/api/dashboard?month=${encodeURIComponent(month)}`, { signal: controller.signal })
      .then(setData)
      .catch((cause) => { if (!controller.signal.aborted) { setData(null); setError(cause instanceof Error ? cause.message : "Governed dashboard unavailable."); } }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [month]);

  return <div className="performance-dashboard">
    <PageHeading eyebrow="GOVERNED PERFORMANCE" title="Business performance" description="What changed this month, what merits attention, and where to investigate next." className="dashboard-heading" />
    <section className="dashboard-period" aria-label="Dashboard period selector"><div><label htmlFor="dashboard-month">Performance month</label><input id="dashboard-month" type="month" value={month} onChange={(event) => { if (event.target.value) setMonth(event.target.value); }} /><small>Currency is shown in dataset-native units; no currency code was supplied.</small></div><p>{data ? `${dashboardPeriodLabel(data.periods.current)} compared with ${dashboardPeriodLabel(data.periods.previous)}` : "Monthly comparison uses the immediately preceding month."}</p></section>
    {loading && <div className="dashboard-state" role="status"><LoaderCircle size={17} className="spinner" />Retrieving governed monthly measurements…</div>}
    {error && !loading && <div className="dashboard-error" role="alert"><CircleHelp size={17} /><div><strong>Performance data could not be retrieved</strong><p>{error}</p><small>No KPI values or trends are displayed without a validated backend response.</small></div></div>}
    {data && !loading && <>
      {data.status === "PARTIAL_MEASUREMENT" && <p className="dashboard-partial" role="status">Some measures are unavailable for one or both months. Missing values are left blank; they are not estimated.</p>}
      <section className="dashboard-kpis" aria-label="Business performance KPIs">{IDS.map((id) => <KpiCard key={id} id={id} metric={data.metrics[id]} data={data} mode={mode} onInvestigate={onInvestigate} />)}</section>
      <section className="dashboard-trend"><SectionHeading eyebrow="MONTHLY PERFORMANCE" title="Current vs previous period" note="Only returned measurements are plotted; each line uses its own scale." /><div className="dashboard-trend-grid">{IDS.filter((id) => data.metrics[id]?.status === "MEASURED").map((id) => <TrendMetric key={id} id={id} metric={data.metrics[id]} periods={data.periods} />)}</div></section>
      <section className="dashboard-attention"><SectionHeading eyebrow="MOVEMENTS TO REVIEW" title="What deserves attention" note="These explicit comparisons are descriptive signals, not causal findings or validated incidents." className="dashboard-section-heading" />
        {data.noteworthy_movements.length ? <div className="movement-list">{data.noteworthy_movements.map((item) => <article className="movement-item" key={item.rule_id}><span className="movement-mark"><ArrowUpRight size={16} /></span><div><h3>{item.title}</h3><p>{data.periods.previous && `${dashboardPeriodLabel(data.periods.previous)} → ${dashboardPeriodLabel(data.periods.current)}`} · Descriptive movement only</p></div><button className="text-button" onClick={() => onInvestigate(item.rule_id === "revenue_up_profit_down" ? `Investigate revenue increasing while contribution profit declined from ${dashboardPeriodLabel(data.periods.previous)} to ${dashboardPeriodLabel(data.periods.current)}` : `Compare late delivery and review score movements from ${dashboardPeriodLabel(data.periods.previous)} to ${dashboardPeriodLabel(data.periods.current)}`)}>Investigate <ArrowRight size={14} /></button></article>)}</div> : <div className="no-movements">{IDS.every((id) => data.metrics[id]?.status === "MEASURED") ? "No configured movement rule was triggered by the available measurements." : "Not enough complete measurements to evaluate the movement rules."}</div>}
      </section>
      {mode === "Analyst" && <section className="dashboard-method"><SectionHeading eyebrow="METHOD & QUALITY" title="Metric definitions and evidence" className="dashboard-section-heading" /><div className="dashboard-method-list">{IDS.map((id) => <AnalystMetric key={id} id={id} metric={data.metrics[id]} />)}</div><ul className="dashboard-limitations">{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul><div className="dashboard-rules"><h3>Movement rules</h3>{data.movement_rules.map((rule) => <p key={rule.rule_id}><code>{rule.rule_id}</code> · {rule.definition}</p>)}</div></section>}
    </>}
  </div>;
}

function KpiCard({ id, metric, data, mode, onInvestigate }: { id: string; metric?: DashboardMetric; data: DashboardData; mode: DashboardMode; onInvestigate: (q: string) => void }) {
  const ready = metric?.status === "MEASURED";
  const deltaSuffix = metric?.delta_unit === "percentage_points" ? " pp" : metric?.delta_unit === "score_points" ? " pts" : metric?.unit === "orders" ? " orders" : "";
  const favorable = id === "late_delivery_rate" ? metric?.direction === "DECREASED" : id === "contribution_margin_pct" || id === "average_review_score" || id === "revenue" || id === "contribution_profit" || id === "orders" ? metric?.direction === "INCREASED" : undefined;
  const investigate = () => ready && onInvestigate(dashboardInvestigationQuestion(id, data.periods.previous, data.periods.current));
  return <article className={`dashboard-kpi ${ready ? "kpi-measured" : "kpi-unavailable"}`} role={mode === "Business" && ready ? "button" : undefined} tabIndex={mode === "Business" && ready ? 0 : undefined} onClick={mode === "Business" ? investigate : undefined} onKeyDown={mode === "Business" && ready ? (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); investigate(); } } : undefined} aria-label={mode === "Business" && ready ? `${metric?.label || title(id)}; investigate comparison` : undefined}>
    <div className="kpi-topline"><h2>{metric?.label || title(id === "contribution_margin_pct" ? "contribution_margin" : id)}</h2>{ready && <span className="kpi-status">Measured</span>}</div>
    {ready ? <><div className="kpi-value">{number(metric.current?.value)}{labelUnit(metric.unit)}</div><div className={`kpi-change ${favorable === undefined ? "" : favorable ? "change-favorable" : metric.direction === "UNCHANGED" ? "" : "change-unfavorable"}`}>{metric.direction === "INCREASED" ? <ArrowUpRight size={14} /> : metric.direction === "DECREASED" ? <ArrowDownRight size={14} /> : null}<span>{number(metric.delta)}{deltaSuffix}</span><small>vs previous month</small></div>{mode === "Analyst" && <div className="kpi-population">{metric.population_note}</div>}</> : <><div className="kpi-unavailable-value">Not available</div><p className="kpi-unavailable-note">{metric?.reason || "No complete governed reading was returned for both months."}</p>{mode === "Analyst" && <p className="kpi-population">No validated measurements were returned.</p>}</>}
    {mode === "Analyst" && ready && <details className="kpi-details"><summary>Definition and provenance</summary>{metric.definition && <p>{metric.definition}</p>}<p>Source: <code>{metric.source || "Source metadata was not supplied with this reading."}</code></p><p>Formula: <code>{metric.formula || "Formula metadata was not supplied with this reading."}</code></p>{metric.policy && <p>Eligibility rule: <code>{metric.policy}</code></p>}{metric.limitations?.map((x) => <p key={x}>{x}</p>)}</details>}
    <ArrowRight className="kpi-open" size={16} aria-hidden="true" />
  </article>;
}

function TrendMetric({ id, metric, periods }: { id: string; metric: DashboardMetric; periods: DashboardData["periods"] }) {
  const before = Number(metric.previous?.value); const after = Number(metric.current?.value);
  const low = Math.min(before, after); const high = Math.max(before, after); const span = high - low || 1;
  const y1 = 30 - ((before - low) / span) * 22; const y2 = 30 - ((after - low) / span) * 22;
  return <div className="trend-metric"><div><strong>{metric.label || title(id)}</strong><small>{dashboardPeriodLabel(periods.previous)} → {dashboardPeriodLabel(periods.current)}</small></div><div className="trend-values"><span>{number(metric.previous?.value)}{labelUnit(metric.unit)}</span><svg viewBox="0 0 54 36" role="img" aria-label={`${dashboardPeriodLabel(periods.previous)} ${number(before)} to ${dashboardPeriodLabel(periods.current)} ${number(after)}`}><path d={`M 5 ${y1} L 49 ${y2}`} /><circle cx="5" cy={y1} r="3" /><circle cx="49" cy={y2} r="3" /></svg><strong>{number(metric.current?.value)}{labelUnit(metric.unit)}</strong></div></div>;
}

function AnalystMetric({ id, metric }: { id: string; metric: DashboardMetric }) {
  if (metric.status !== "MEASURED") return <article><h3>{title(id)}</h3><p>Not measured for both periods: {metric.reason}</p></article>;
  return <article><h3>{metric.label}</h3>{metric.definition && <p>{metric.definition}</p>}<div><span>Period value</span>{number(metric.previous?.value)} → {number(metric.current?.value)} {metric.unit}</div><p>Previous eligible population · {populationSummary(metric.eligibility?.previous ?? metric.previous?.population)}</p><p>Current eligible population · {populationSummary(metric.eligibility?.current ?? metric.current?.population)}</p>{metric.source && <p>Source · {metric.source}</p>}{metric.policy && <p>Eligibility rule · {metric.policy}</p>}{metric.limitations?.map((x) => <p key={x}>{x}</p>)}</article>;
}
