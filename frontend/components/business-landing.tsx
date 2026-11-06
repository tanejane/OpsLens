"use client";

import { useEffect, useState } from "react";
import { ArrowRight, ArrowUpRight, BookOpen, RefreshCw } from "lucide-react";
import type { DashboardData, DashboardMetric } from "./BusinessDashboard";
import type { SessionSnapshot } from "../lib/investigation-session";
import { requestJson } from "../lib/api-client";
import { dashboardPeriodLabel } from "../lib/dashboard";
import { disposition, finiteReading, formatReading, isMeasured, replayUrl, validDashboard } from "../lib/business-overview";
import { ComparisonBars, MetricChange, OverviewPanel } from "./business-primitives";

type Props = { onInvestigate: (question: string) => void; history: SessionSnapshot["history"]; onOpen: (record: Record<string, unknown>) => void; sessionReady: boolean; sessionError?: string };

export function BusinessLanding({ onInvestigate, history, onOpen, sessionReady, sessionError }: Props) {
  const [month, setMonth] = useState("2018-06");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [question, setQuestion] = useState("");
  
  useEffect(() => {
    let active = true;

    setLoading(true);
    setError("");
    setData(null);

    requestJson<DashboardData>(
      `/api/dashboard?month=${encodeURIComponent(month)}`
    )
      .then((value) => {
        if (!active) return;

        if (!validDashboard(value, month)) {
          throw new Error(
            "The returned reporting period could not be verified."
          );
        }

        setData(value);
      })
      .catch((cause) => {
        if (!active) return;

        setError(
          cause instanceof Error
            ? cause.message
            : "Performance data unavailable."
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [month, attempt]);

  const previous = data ? dashboardPeriodLabel(data.periods.previous) : "Previous month";
  const current = data ? dashboardPeriodLabel(data.periods.current) : "Selected month";
  const investigatePeriod = data ? `Compare finance, late delivery and review scores from ${previous} to ${current}` : "";
  const metrics = data?.metrics ?? {};

  return <div className="business-overview">
    <header className="overview-heading"><div><p className="overview-kicker">Business view</p><h1>Performance, in perspective.</h1></div><div className="overview-period"><label htmlFor="overview-month">Reporting month</label><input id="overview-month" type="month" value={month} onInput={e => { if (e.currentTarget.value) setMonth(e.currentTarget.value); }} onChange={e => { if (e.target.value) setMonth(e.target.value); }} /></div></header>
    <div className="overview-period-line"><span>{data && !loading ? `${current} compared with ${previous}` : loading ? "Loading reporting period…" : "Reporting period unavailable"}</span><span>Historical data</span></div>
    {error && <div className="overview-alert" role="alert"><div><strong>Performance data unavailable</strong><p>{error}</p></div><button className="overview-link" onClick={() => setAttempt(n => n + 1)}><RefreshCw size={14} />Retry</button></div>}
    {data?.status === "PARTIAL_MEASUREMENT" && <p className="overview-notice" role="status">Some comparisons are unavailable. Missing readings are not estimated.</p>}
    <div className="overview-grid">
      <OverviewPanel title="Financial performance" className="overview-hero">
        <div aria-busy={loading} className="overview-revenue"><span>Revenue</span><div className={`overview-hero-value ${loading ? "overview-loading" : ""}`}>{loading ? <span aria-label="Loading revenue">—</span> : isMeasured(metrics.revenue) ? formatReading(metrics.revenue.current?.value) : "—"}</div>{!loading && <MetricChange metric={metrics.revenue} />}</div>
        <div className="overview-finance-stats">{[["contribution_profit", "Contribution profit"], ["contribution_margin_pct", "Contribution margin"], ["orders", "Placed orders"]].map(([id, name]) => <div key={id}><h3>{name}</h3><strong>{loading ? "—" : isMeasured(metrics[id]) ? `${formatReading(metrics[id].current?.value)}${id === "contribution_margin_pct" ? "%" : ""}` : "—"}</strong>{!loading && <MetricChange metric={metrics[id]} />}</div>)}</div>
        <div className="overview-hero-foot"><span>Dataset-native currency · modeled costs</span><button className="overview-icon-link" disabled={!data || loading} onClick={() => onInvestigate(investigatePeriod)} aria-label="Prepare investigation for these reporting periods"><ArrowUpRight size={19} /></button></div>
      </OverviewPanel>

      <OverviewPanel title="A closer look." className="overview-entry" action={<ArrowUpRight size={21} aria-hidden="true" />}>
        <p>Start with a question.</p>
        <form onSubmit={e => { e.preventDefault(); if (question.trim()) onInvestigate(question.trim()); }}>
          <label className="overview-sr-only" htmlFor="overview-question">Business question</label><textarea id="overview-question" value={question} maxLength={500} onChange={e => setQuestion(e.target.value)} placeholder="What would you like to understand? Include a metric and period." rows={3} />
          <button className="overview-primary" disabled={!question.trim() || !sessionReady}>Prepare investigation <ArrowRight size={16} /></button>
        </form>
        <div className="overview-starts"><button disabled={!data || loading || !sessionReady} onClick={() => onInvestigate(investigatePeriod)}>Review this month’s performance <ArrowRight size={14} /></button><button disabled={!data || loading || !sessionReady} onClick={() => onInvestigate(`What was the late delivery rate in ${current}?`)}>Look at delivery <ArrowRight size={14} /></button></div>
        <small>Review your question before running it.</small>
      </OverviewPanel>

      <OverviewPanel title="Financial movement" className="overview-movement" action={<span className="overview-muted">Month over month</span>}>
        {loading ? <LoadingBlock /> : <><ComparisonBars name="Revenue" metric={metrics.revenue} previous={previous} current={current} /><ComparisonBars name="Contribution profit" metric={metrics.contribution_profit} previous={previous} current={current} />
        <p className="overview-chart-note">Dataset currency · each measure has its own zero-based scale</p>
        {data?.noteworthy_movements?.map(item => <p className="overview-observation" key={item.rule_id}>{item.title}<small>Observed movement · not a causal explanation</small></p>)}
        <div className="overview-cost-entry"><div><strong>Cost components</strong><small>Inspect accounting contributions in an investigation.</small></div><button className="overview-icon-link" disabled={!data} onClick={() => onInvestigate(investigatePeriod)} aria-label="Prepare a governed accounting investigation"><ArrowRight size={17} /></button></div></>}
      </OverviewPanel>

      <OverviewPanel title="Operations & customer experience" className="overview-operations">
        {loading ? <LoadingBlock /> : <><OperationalMetric name="Late delivery" metric={metrics.late_delivery_rate} suffix="%" populationKey="lateness_eligible_orders" populationLabel="orders with delivery timestamps" /><OperationalMetric name="Customer review score" metric={metrics.average_review_score} suffix=" / 5" populationKey="reviewed_orders" populationLabel="reviewed orders" /></>}
        <p className="overview-chart-note">Purchase-month cohorts · eligible populations differ</p>
      </OverviewPanel>
    </div>

    <OverviewPanel title="Recent investigations" className="overview-history" action={<span className="overview-muted">This session</span>}>
      {sessionError && <p className="overview-notice" role="alert">{sessionError}</p>}
      {!sessionReady ? <p className="overview-empty" role="status">Restoring your session…</p> : !history.length ? <div className="overview-empty"><BookOpen size={19} aria-hidden="true" /><p>No investigations in this session.</p><button className="overview-link" onClick={() => document.getElementById("overview-question")?.focus()}>Ask a question <ArrowRight size={14} /></button></div> : <div className="overview-history-list">{history.slice(-4).reverse().map(({ turn, canonical_result: record }) => {
        const replay = replayUrl(record);
        return <article className="overview-history-row" key={turn}><span className="overview-turn">{String(turn).padStart(2, "0")}</span><button className="overview-history-open" onClick={() => onOpen(record)}><strong>{String(record.question || "Investigation")}</strong><small>{disposition(record)}</small></button><div className="overview-history-actions">{replay && <a href={replay} target="_blank" rel="noreferrer" aria-label={`Saved evidence for investigation ${turn} (JSON, opens in new tab)`}>Saved evidence <ArrowUpRight size={13} /></a>}<button className="overview-icon-link" aria-label={`Open investigation ${turn}`} onClick={() => onOpen(record)}><ArrowRight size={17} /></button></div></article>;
      })}</div>}
      {!!history.length && <p className="overview-chart-note">Saved evidence is historical, not revalidated. Session history expires or clears on reset.</p>}
    </OverviewPanel>
    {data && <details className="overview-method"><summary>Reporting basis & limitations</summary><p>Revenue and profit use financially represented orders; placed orders use all placed orders. Cost and operational adjustments may be synthetic. Display values are rounded to two decimals; no currency conversion is applied.</p>{Object.entries(data.metrics).map(([id, metric]) => <p key={id}><strong>{metric.label || id.replaceAll("_", " ")}: </strong>{metric.status === "UNAVAILABLE" ? metric.reason : metric.population_note || metric.definition}{metric.source && <> Source: {metric.source}.</>}</p>)}{data.limitations?.map(item => <p key={item}>{item}</p>)}</details>}
  </div>;
}

function LoadingBlock() { return <div className="overview-loading-block" role="status"><span>Loading measurements…</span><i /><i /></div>; }

function OperationalMetric({ name, metric, suffix, populationKey, populationLabel }: { name: string; metric?: DashboardMetric; suffix: string; populationKey: string; populationLabel: string }) {
  const ready = isMeasured(metric);
  const count = metric?.current?.population?.[populationKey] ?? metric?.eligibility?.current?.[populationKey];
  return <div className="overview-operation"><div className="overview-operation-head"><h3>{name}</h3><MetricChange metric={metric} /></div><strong className="overview-operation-value">{ready ? formatReading(metric?.current?.value) : "—"}<span>{ready ? suffix : ""}</span></strong><p>{ready ? finiteReading(count) !== null ? `${formatReading(count, 0)} ${populationLabel}` : metric?.population_note || "Eligible population not supplied" : metric?.reason || "No complete comparison available"}</p><details><summary>Measurement basis</summary><p>{metric?.definition}</p>{metric?.limitations?.map(item => <p key={item}>{item}</p>)}</details></div>;
}
