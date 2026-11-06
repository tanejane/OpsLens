import type { NormalizedInvestigation } from "../lib/investigation";

/** Both workspaces inspect the same canonical record, without a second schema. */
export function InvestigationEvidence({ report, mode }: { report: NormalizedInvestigation; mode: "Business" | "Analyst" }) {
  return <details className="trace-details" open={mode === "Analyst"}>
    <summary>Complete investigation evidence</summary>
    <p>Original returned record, including stage-specific limitations. Retention does not certify missing evidence or authorize new queries. Paths identify where each value was returned.</p>
    <dl>{report.evidenceEntries.filter(entry => mode === 'Analyst' || !/\/(observability|model_calls)(\/|$)/.test(entry.path)).map((entry) => <div key={entry.path}>
      <dt><code style={{ overflowWrap: "anywhere" }}>{entry.path}</code></dt>
      <dd style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{entry.value}</dd>
    </div>)}</dl>
  </details>;
}
