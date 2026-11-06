"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, BookOpenText, ChevronDown, Database, LoaderCircle, Search, ShieldCheck } from "lucide-react";
import { requestJson } from "../lib/api-client";
import { PageHeading, SectionHeading } from "./ui";

type Metric = {
  metric_name: string; domain: string; business_definition: string; formula: string;
  grain: string; source_view: string; time_field: string; dimensions: string[]; known_limitations: string[];
};
type Capability = { name: string; route: string; state: string; metric_ids: string[]; sources: string[] };
type Audit = { artifact: string; contract: string; time_basis: string; status: string; months: { month: string; orders: number; delivery_id_set_equal: boolean; review_id_set_equal: boolean }[]; scope: string };
type EvidencePayload = { metrics: Metric[]; cohort_audits: Audit[]; limitations: string[] };
const title = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const DOMAIN_NAMES: Record<string, string> = { cx: "Customer Experience", behavior: "Behavior", inventory: "Inventory", finance: "Finance", commerce: "Commerce", operations: "Operations", marketing: "Marketing", knowledge: "Knowledge" };
const domainName = (value: string) => DOMAIN_NAMES[value.toLowerCase()] || title(value);

export function MetricsExplorer() {
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("all");
  const [selectedName, setSelectedName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    requestJson<{ metrics?: Metric[]; execution_capabilities?: Capability[] }>("/api/metrics")
      .then((body) => { setMetrics(Array.isArray(body.metrics) ? body.metrics : []); setCapabilities(Array.isArray(body.execution_capabilities) ? body.execution_capabilities : []); })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Metric catalog unavailable.")).finally(() => setLoading(false));
  }, []);
  const domains = useMemo(() => [...new Set(metrics.map((metric) => metric.domain))].sort(), [metrics]);
  const visible = metrics.filter((metric) => (domain === "all" || metric.domain === domain) && `${metric.metric_name} ${metric.domain} ${metric.business_definition} ${metric.source_view}`.toLowerCase().includes(query.toLowerCase()));
  const groups = [...new Set(visible.map((metric) => metric.domain))];
  const selected = visible.find((metric) => metric.metric_name === selectedName) || visible[0];
  const selectedCapabilities = selected ? capabilities.filter((entry) => entry.metric_ids.includes(selected.metric_name)) : [];
  const executionGroups = [
    ["Home dashboard", capabilities.filter((item) => item.name === "Home monthly comparison")],
    ["Finance", capabilities.filter((item) => item.name === "Finance metric compiler")],
    ["Operations", capabilities.filter((item) => item.name === "Delivery metric compiler")],
    ["Customer Experience", capabilities.filter((item) => item.name === "Satisfaction metric compiler")],
    ["Product & category", capabilities.filter((item) => item.name === "Product/category item metric compiler")],
  ] as const;
  useEffect(() => { if (selected && selectedName !== selected.metric_name) setSelectedName(selected.metric_name); }, [selected, selectedName]);

  return <div className="metadata-page">
    <PageHeading eyebrow="GOVERNED DEFINITIONS" title="Metrics" description="Search the approved catalog. A definition describes a measure; it does not itself prove a live data path." />
    <div className="metadata-toolbar"><label className="metadata-search"><Search size={15} /><input aria-label="Search metrics" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search metric definitions" /></label><label className="domain-filter"><span>Domain</span><select value={domain} onChange={(event) => setDomain(event.target.value)}><option value="all">All domains</option>{domains.map((item) => <option value={item} key={item}>{domainName(item)}</option>)}</select></label><span className="metadata-count">{visible.length} of {metrics.length} metrics</span></div>
    {loading && <div className="metadata-state"><LoaderCircle size={17} className="spinner" />Loading approved metric definitions…</div>}
    {error && <div className="metadata-error" role="alert"><AlertCircle size={16} />{error}</div>}
    {!loading && !error && visible.length === 0 && <div className="metadata-state">No catalog metrics match this search.</div>}
    {!loading && !error && visible.length > 0 && <div className="metric-browser">
      <nav className="metric-groups" aria-label="Metric groups">{groups.map((group) => <section key={group}><h2>{domainName(group)}</h2>{visible.filter((metric) => metric.domain === group).map((metric) => <button key={metric.metric_name} type="button" aria-pressed={selected?.metric_name === metric.metric_name} onClick={() => setSelectedName(metric.metric_name)}><span>{title(metric.metric_name)}</span><small>{metric.source_view}</small></button>)}</section>)}</nav>
      {selected && <article className="metric-detail-panel"><header><div><span className="eyebrow">{domainName(selected.domain)} · CATALOG DEFINITION</span><h2>{title(selected.metric_name)}</h2></div><span className="catalog-tag">Governed metadata</span></header><p className="metric-purpose">{selected.business_definition}</p>
        <dl className="metric-detail-grid"><div><dt>Formula</dt><dd><code>{selected.formula || "Not specified in catalog"}</code></dd></div><div><dt>Unit</dt><dd>Not specified in catalog</dd></div><div><dt>Grain</dt><dd>{selected.grain || "Not specified in catalog"}</dd></div><div><dt>Time basis</dt><dd><code>{selected.time_field || "Not specified in catalog"}</code></dd></div><div><dt>Eligible population</dt><dd>Not specified in catalog; grain shown above.</dd></div><div><dt>Dimensions</dt><dd>{selected.dimensions?.length ? selected.dimensions.join(" · ") : "None listed"}</dd></div><div><dt>Source view</dt><dd><code>{selected.source_view || "Not specified in catalog"}</code></dd></div></dl>
        <section className="metric-execution"><h3>Registered execution paths</h3><p>Compiler registration describes code capability only; live availability depends on API, MCP permissions and PostgreSQL.</p>{selectedCapabilities.length ? selectedCapabilities.map((item) => <div key={item.name}><strong>{item.name}</strong><span>{item.route} · {item.state.replaceAll("_", " ")}</span><small>Sources: {item.sources.join(" · ")}</small></div>) : <p className="catalog-only">No registered application executor has this exact metric identifier. The catalog definition remains available for reference.</p>}</section>
        {selected.known_limitations.length > 0 && <section className="metric-limitations"><h3>Known limitations</h3><ul>{selected.known_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></section>}
      </article>}
    </div>}
    {!loading && !error && capabilities.length > 0 && <section className="execution-registry"><SectionHeading eyebrow="APPLICATION ROUTES" title="Registered execution capabilities" note="Derived from the existing governed compiler registries. These are code paths, not a live database-health signal or a claim that each catalog definition is executable." className="metadata-section-heading" /><div className="execution-registry-grid">{executionGroups.filter(([, items]) => items.length > 0).map(([group, items]) => <section key={group}><h3>{group}</h3>{items.map((item) => <article key={item.name}><strong>{item.name}</strong><span>{item.route}</span><p>{item.metric_ids.join(" · ")}</p><small>{item.sources.join(" · ")}</small><em>{item.state.replaceAll("_", " ")}</em></article>)}</section>)}</div></section>}
    <p className="metadata-foot"><ShieldCheck size={14} />Selecting a definition does not run a query. This explorer exposes no SQL, arbitrary aggregation or filtering controls.</p>
  </div>;
}

export function EvidenceExplorer() {
  const [payload, setPayload] = useState<EvidencePayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => { requestJson<EvidencePayload>("/api/evidence").then(setPayload).catch((cause) => setError(cause instanceof Error ? cause.message : "Evidence metadata unavailable.")).finally(() => setLoading(false)); }, []);
  return <div className="metadata-page evidence-page">
    <PageHeading eyebrow="PROVENANCE & AUDIT" title="Evidence & sources" description="Source definitions and validated audit summaries from saved repository artifacts." />
    {loading && <div className="metadata-state"><LoaderCircle size={17} className="spinner" />Loading source metadata…</div>}
    {error && <div className="metadata-error" role="alert"><AlertCircle size={16} />{error}</div>}
    {payload && <>
      <section className="evidence-catalog-section"><SectionHeading eyebrow="METRIC PROVENANCE" title="Governed source views" note="These are catalog sources; the execution registry above is separate from source metadata." className="metadata-section-heading" /><div className="source-catalog">{payload.metrics.map((metric) => <article key={metric.metric_name}><span className="source-icon"><Database size={15} /></span><div><h3>{title(metric.metric_name)}</h3><p>{metric.source_view} · {domainName(metric.domain)} · time field {metric.time_field}</p><small>{metric.grain}</small></div></article>)}</div></section>
      <section className="evidence-catalog-section"><SectionHeading eyebrow="EXISTING AUDIT ARTIFACTS" title="Order cohort reconciliation" note="Exact cohort set evidence, validated using the repository assessor. These audits are read only and do not establish causation." className="metadata-section-heading" />
        {payload.cohort_audits.length ? <div className="audit-catalog">{payload.cohort_audits.map((audit) => <details key={audit.artifact} className="audit-item"><summary><span className="audit-status"><i />{title(audit.status)}</span><code>{audit.contract}</code><ChevronDown size={15} /></summary><div className="audit-detail"><p>{audit.scope} · {title(audit.time_basis)} · source artifact <code>{audit.artifact}</code></p><div className="audit-months">{audit.months.map((month) => <div key={month.month}><strong>{month.month}</strong><span>{month.orders.toLocaleString()} reconciled orders</span><small>Delivery set {month.delivery_id_set_equal ? "matched" : "unverified"} · Review set {month.review_id_set_equal ? "matched" : "unverified"}</small></div>)}</div><p className="audit-limit">Read only · not approved for MCP execution · does not prove finance population equality or causation.</p></div></details>)}</div> : <div className="metadata-state">No validated cohort audit artifact is currently available.</div>}
      </section>
      {payload.limitations.length > 0 && <div className="metadata-limitations"><BookOpenText size={15} /><div><strong>Evidence boundaries</strong><ul>{payload.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div></div>}
    </>}
  </div>;
}
