import type { NormalizedInvestigation } from "../lib/investigation";
import { InvestigationEvidence } from "./investigation-evidence";
type Cohort = { orders: number; reviewed: number; missing_reviews: number; low: number; score_sum: string; multi_review_orders: number; average_score: string | null; low_rating_rate_pct: string | null; review_coverage_pct: string | null };
type Comparison = { reason: string; limitations: string[]; supporting_analyses?: {capability:string; conclusion:string; evidence:unknown}[]; orchestration?: unknown; evidence: { period: string[]; cohorts: Record<string, Cohort>; methodology: string; sources: string[]; total_orders: number; missing_review_rows: number } };

export function DeliveryReviewComparison({ report, mode }: { report: NormalizedInvestigation; mode: "Business" | "Analyst" }) {
  const payload = report.canonicalRecord.payload as unknown as Comparison;
  const evidence = payload.evidence;
  const cohorts = evidence.cohorts;
  const number = (value: unknown) => value == null ? "Not available" : Number(value).toFixed(2);
  return <article className="report" aria-live="polite">
    <section className="report-section"><h2>Do late orders receive different ratings?</h2><p>Orders purchased from {evidence.period[0]} to {evidence.period[1]} (exclusive).</p><p>{payload.reason}</p>
      <div className="metric-grid">{["late", "on_time"].map(key => <div className="metric-card" key={key}><h3>{key === "late" ? "Late" : "On-time"} orders</h3><strong>{number(cohorts[key]?.average_score)} / 5</strong><p>{cohorts[key]?.reviewed ?? 0} reviewed of {cohorts[key]?.orders ?? 0} orders</p><p>{number(cohorts[key]?.low_rating_rate_pct)}% low ratings · {number(cohorts[key]?.review_coverage_pct)}% reviewed</p></div>)}</div>
      <h3>Average order rating</h3><svg viewBox="0 0 600 120" role="img" aria-label="Late and on-time mean ratings on a zero to five scale" style={{ width: "100%", maxWidth: 700 }}>{["late", "on_time"].map((key,i) => <g key={key}><text x="0" y={30+i*45}>{key === "late" ? "Late" : "On-time"}</text><rect x="100" y={12+i*45} width={Number(cohorts[key]?.average_score ?? 0)*75} height="24" fill={i ? "#698373" : "#b47b54"} /><text x="490" y={30+i*45}>{number(cohorts[key]?.average_score)}</text></g>)}</svg>
      <p>Lower ratings and differences in review coverage deserve attention together. This comparison does not establish that delays caused the rating difference.</p>
      <h3>Next investigation</h3><p>Compare another purchase month to see whether this pattern persists. Review missingness before drawing broader conclusions.</p>
    </section>
    {mode === "Analyst" && <section className="report-section"><h3>Cohorts and denominators</h3><table><thead><tr><th>Cohort</th><th>Orders</th><th>Reviewed</th><th>Missing reviews</th><th>Low ratings</th><th>Score sum</th><th>Multiple reviews</th></tr></thead><tbody>{Object.entries(cohorts).map(([key,c]) => <tr key={key}><td>{key}</td>{[c.orders,c.reviewed,c.missing_reviews,c.low,c.score_sum,c.multi_review_orders].map((v,i)=><td key={i}>{String(v)}</td>)}</tr>)}</tbody></table><p>{evidence.methodology}</p><p>Sources: {evidence.sources.join(", ")}. Total orders: {evidence.total_orders}; missing review-view rows: {evidence.missing_review_rows}.</p></section>}
    {payload.supporting_analyses?.length ? <section className="report-section"><h3>What the additional evidence shows</h3>{payload.supporting_analyses.map(s=><div key={s.capability}><p>{s.conclusion}</p>{mode === "Analyst" && <details><summary>Supporting measurement and denominator</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(s.evidence,null,2)}</pre></details>}</div>)}</section> : null}
    {mode === "Analyst" && payload.orchestration ? <details className="trace-details"><summary>Investigation steps</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(payload.orchestration,null,2)}</pre></details> : null}
    <section className="report-section"><h3>Scope of the findings</h3><ul>{payload.limitations.map((s:string)=><li key={s}>{s}</li>)}</ul></section>
    <InvestigationEvidence report={report} mode={mode} />
  </article>;
}
