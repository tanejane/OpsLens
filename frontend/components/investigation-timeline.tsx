import type { JsonObject, NormalizedInvestigation } from "../lib/investigation";

type Props = { report: NormalizedInvestigation; mode?: "Business" | "Analyst" };
type TraceEvent = {
  id: string;
  source: string;
  source_index: number;
  stage: "decision" | "tool_execution";
  capability?: string | null;
  decision?: string | null;
  reason?: string | null;
  tool?: string | null;
  outcome?: string | null;
  latency_ms?: number | null;
  error_type?: string | null;
};
type StopEvent = { id: string; source: string; reason: string; stage: "stop" };

function obj(value: unknown): JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as JsonObject : {};
}
function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
function str(value: unknown): string {
  return typeof value === "string" ? value : "";
}
function human(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
}
function brief(value: string, limit = 320): string {
  return value.length > limit ? `${value.slice(0, limit)}…` : value;
}
function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function parseTrace(payload: JsonObject) {
  const v2 = obj(payload.agent_trace_v2);
  if (v2.schema_version === "opslens.agent_trace.v2" &&
      v2.ordering === "SOURCE_LOCAL_ONLY" &&
      v2.global_sequence_verified === false &&
      Array.isArray(v2.events) && Array.isArray(v2.stop_conditions)) {
    const events: TraceEvent[] = array(v2.events).map(obj).filter(row =>
      typeof row.id === "string" && typeof row.source === "string" &&
      typeof row.source_index === "number" &&
      (row.stage === "decision" || row.stage === "tool_execution")
    ).map(row => ({
      id: str(row.id), source: str(row.source), source_index: Number(row.source_index),
      stage: row.stage as TraceEvent["stage"],
      capability: str(row.capability), decision: str(row.decision),
      reason: str(row.reason), tool: str(row.tool), outcome: str(row.outcome),
      latency_ms: finite(row.latency_ms) ? row.latency_ms : null,
      error_type: str(row.error_type),
    }));
    const stops: StopEvent[] = array(v2.stop_conditions).map(obj).filter(row =>
      typeof row.id === "string" && typeof row.source === "string" &&
      typeof row.reason === "string"
    ).map(row => ({ id: str(row.id), source: str(row.source),
      reason: str(row.reason), stage: "stop" }));
    return { version: "v2" as const, events, stops };
  }

  // Older saved records have no Trace V2. This fallback shows each recorded
  // stream separately without claiming a unified chronological sequence.
  const finance = obj(obj(payload.domain_results).finance);
  const streams = [
    ["orchestration", array(obj(payload.orchestration).trace)],
    ["adaptive", array(obj(payload.adaptive).trace)],
    ["finance_adaptive", array(obj(finance.adaptive).trace)],
    ["execution", array(payload.execution_trace)],
  ] as const;
  const events: TraceEvent[] = [];
  streams.forEach(([source, records]) => records.forEach((raw, index) => {
    const row = obj(raw);
    const tool = str(row.tool);
    const capability = str(row.capability);
    const decision = str(row.decision);
    if (!tool && !capability && !decision) return;
    events.push({ id: `${source}:${index}`, source, source_index: index,
      stage: tool ? "tool_execution" : "decision", tool, capability, decision,
      reason: str(row.reason), outcome: str(row.outcome), error_type: str(row.error_type),
      latency_ms: finite(row.latency_ms) ? row.latency_ms : null });
  }));
  const stops: StopEvent[] = [];
  ([
    ["orchestration", obj(payload.orchestration)],
    ["adaptive", obj(payload.adaptive)],
    ["finance_adaptive", obj(finance.adaptive)],
  ] as const).forEach(([source, info]) => {
    const reason = str(info.stop_reason);
    if (reason) stops.push({ id: `${source}:stop`, source, stage: "stop", reason });
  });
  return { version: "legacy" as const, events, stops };
}

const muted = { fontSize: 12, lineHeight: 1.65, color: "var(--overview-muted, #706e62)" } as const;
const sectionTitle = { fontSize: 13, fontWeight: 600, margin: "0 0 10px" } as const;

export function InvestigationTimeline({ report }: Props) {
  const payload = obj(report.canonicalRecord.payload);
  const trace = parseTrace(payload);
  const audit = obj(payload.observability);
  const provenance = obj(payload.context_provenance);
  const runId = str(audit.run_id);
  const sessionId = str(provenance.session_id);
  const decisions = trace.events.filter(event => event.stage === "decision");
  const tools = trace.events.filter(event => event.stage === "tool_execution");
  const hasData = trace.events.length > 0 || trace.stops.length > 0 ||
    Boolean(runId || str(audit.validation_decision));

  const toolRows = (items: TraceEvent[]) => items.map(event => (
    <li key={event.id} style={{ padding: "9px 0", borderBottom: "1px solid var(--overview-line, #dcd8cd)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <strong style={{ fontSize: 12, fontWeight: 600 }}>{human(event.tool || "Recorded tool")}</strong>
        <span style={muted}>{human(event.outcome || "Recorded")}
          {finite(event.latency_ms) ? ` · ${event.latency_ms.toFixed(1)} ms` : ""}
        </span>
      </div>
      <div style={{ ...muted, marginTop: 3 }}>
        {human(event.source)} · recorded call #{event.source_index + 1}
        {event.error_type ? ` · Error: ${human(event.error_type)}` : ""}
      </div>
    </li>
  ));

  return (
    <details className="trace-details agent-execution-timeline" style={{ marginTop: 22,
      padding: "22px 24px", border: "1px solid var(--overview-line, #dcd8cd)", borderRadius: 5 }}>
      <summary style={{ cursor: "pointer", fontSize: 14, fontWeight: 600 }}>Agent execution</summary>
      <div style={{ display: "grid", gap: 22, marginTop: 18 }}>
        <p style={{ ...muted, margin: 0 }}>
          {trace.version === "v2" ? "Trace V2 · Recorded evidence" : "Legacy recorded evidence"}
          {" · "}Events are ordered only within their original source stream.
          No cross-stream chronology is asserted.
        </p>
        {(runId || str(audit.validation_decision)) && (
          <div style={muted}>
            {str(audit.validation_decision) && <p style={{ margin: "0 0 4px" }}>
              Validation: {human(str(audit.validation_decision))}</p>}
            {finite(audit.latency_ms) && <p style={{ margin: "0 0 4px" }}>
              Recorded duration: {audit.latency_ms.toFixed(1)} ms</p>}
            {runId && <p style={{ margin: 0 }}>Run: {runId}</p>}
          </div>
        )}
        {!hasData && <p style={muted}>No execution events were returned for this investigation.
          This does not prove that no internal actions occurred.</p>}
        {decisions.length > 0 && <section>
          <h3 style={sectionTitle}>Coordinator decisions ({decisions.length})</h3>
          <ol style={{ margin: 0, paddingLeft: 21, display: "grid", gap: 14 }}>
            {decisions.map(event => <li key={event.id}>
              <strong style={{ fontSize: 12, fontWeight: 600 }}>
                {human(event.capability || "Recorded decision")}
              </strong>
              <p style={{ ...muted, margin: "4px 0" }}>
                {human(event.source)} · step #{event.source_index + 1}
                {event.decision ? ` · ${human(event.decision)}` : ""}
              </p>
              {event.reason && <p style={{ ...muted, margin: 0 }}>{brief(event.reason)}</p>}
            </li>)}
          </ol>
        </section>}
        {tools.length > 0 && <section>
          <h3 style={sectionTitle}>Recorded tool executions ({tools.length})</h3>
          <p style={{ ...muted, margin: "0 0 10px" }}>
            Each numbered row is a distinct recorded entry. Repeated tool names can be
            legitimate separate calls. Raw SQL and tool responses are not shown here.
          </p>
          <ol style={{ margin: 0, paddingLeft: 21, listStyle: "none" }}>
            {toolRows(tools.slice(0, 6))}
          </ol>
          {tools.length > 6 && <details style={{ marginTop: 12 }}>
            <summary style={{ cursor: "pointer", fontSize: 12 }}>
              Show remaining {tools.length - 6} recorded calls
            </summary>
            <ol style={{ margin: "8px 0 0", paddingLeft: 21, listStyle: "none" }}>
              {toolRows(tools.slice(6))}
            </ol>
          </details>}
        </section>}
        {trace.stops.length > 0 && <section>
          <h3 style={sectionTitle}>Recorded stop conditions</h3>
          <ul style={{ ...muted, margin: 0, paddingLeft: 20 }}>
            {trace.stops.map(stop => <li key={stop.id}>
              {human(stop.source)}: {brief(stop.reason, 400)}
            </li>)}
          </ul>
        </section>}
        {runId && sessionId && audit.persistence === "SAVED" && <p style={{ margin: 0 }}>
          <a href={`/api/investigation-sessions/${encodeURIComponent(sessionId)}/runs/${encodeURIComponent(runId)}/replay`}
            target="_blank" rel="noreferrer"
            style={{ ...muted, color: "var(--overview-olive, #626b50)", textDecoration: "underline" }}>
            Open saved canonical evidence (JSON)
          </a>
        </p>}
        <p style={{ ...muted, margin: 0, borderTop: "1px solid var(--overview-line, #dcd8cd)", paddingTop: 12 }}>
          This view projects only returned events. A source-local event ID is not a
          globally unique execution identifier. Replay retrieves saved evidence without
          re-executing MCP tools or validating against current database state.
        </p>
      </div>
    </details>
  );
}
