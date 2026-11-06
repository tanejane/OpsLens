export type JsonObject = Record<string, unknown>;
export const INVESTIGATION_SCHEMA = "opslens.investigation.v1";
export type CanonicalInvestigation = { schema_version: string; question: string; payload: JsonObject; number_encodings?: Record<string, "decimal" | "integer"> };
export type EvidenceEntry = { path: string; value: string };

/** JSON Pointer paths retain scope and array order; these are not invented evidence IDs. */
export function evidenceEntries(value: unknown, path = ""): EvidenceEntry[] {
  if (value && typeof value === "object" && Object.keys(value).length) {
    return Object.entries(value).flatMap(([key, child]) => evidenceEntries(child, `${path}/${key.replaceAll("~", "~0").replaceAll("/", "~1")}`));
  }
  return [{ path: path || "/", value: JSON.stringify(value) ?? "undefined" }];
}
export type FindingStatus = "measured" | "evidence_gap" | "clarification" | "failed" | "unverified";
export type EvidenceCoverage = "complete" | "partial" | "evidence_gap" | "clarification" | "failed" | "unsupported";
export type Measure = {
  id: string; status: string; value?: unknown; before?: unknown; after?: unknown; delta?: unknown; unit?: string; deltaUnit?: string;
  period?: unknown; population?: JsonObject; source?: string; policy?: string; timeBasis?: string; limitations: string[];
  beforeEvidence?: JsonObject; afterEvidence?: JsonObject; definition?: string;
};
export type PerOrderCostMeasure = {
  component: string; beforePerOrder: unknown; afterPerOrder: unknown; changePerOrder: unknown;
};
export type PerOrderCostEvidence = {
  status: string; populationBasis: string; beforeOrders?: number; afterOrders?: number;
  components: PerOrderCostMeasure[]; limitations: string[]; validated: boolean;
};
export type NormalizedInvestigation = {
  canonicalRecord: CanonicalInvestigation; evidenceEntries: EvidenceEntry[]; graphRows: JsonObject[];
  accountingBridge: JsonObject[]; stopReasons: EvidenceEntry[];
  status: FindingStatus; rawStatus: string; coverage: EvidenceCoverage; route: string; title: string; question: string; periods: JsonObject; domains: string[];
  findings: string[]; measures: Measure[]; financialPremise: JsonObject; accountingHypotheses: JsonObject[];
  cohortEvidence: JsonObject; evidenceRequirements: string[]; nextValidations: string[]; limitations: string[];
  untestedHypotheses: JsonObject; toolTrace: JsonObject[]; causalClaim: boolean | null; reason: string;
  businessImplications: string[]; productContext: JsonObject; sourceEvidence: JsonObject[];
  accountingReconciliation: JsonObject;
  perOrderCostEvidence: PerOrderCostEvidence;
  explanationPlan: JsonObject;
};

const obj = (v: unknown): JsonObject => v && typeof v === "object" && !Array.isArray(v) ? v as JsonObject : {};
const arr = (v: unknown): unknown[] => Array.isArray(v) ? v : [];
const str = (v: unknown): string => typeof v === "string" ? v : "";
const numeric = (v: unknown): number | undefined => {
  if (typeof v !== "number" && typeof v !== "string" || typeof v === "string" && !v.trim()) return undefined;
  const parsed = Number(v);
  return Number.isFinite(parsed) ? parsed : undefined;
};
const strings = (v: unknown): string[] => arr(v).filter((x): x is string => typeof x === "string");
const mergeStrings = (...xs: unknown[]): string[] => [...new Set(xs.flatMap(strings))];

export function plainLanguageLimitation(value: string): string {
  const s = value.toLowerCase();
  if (s.includes("measured accounting movements, not causal root causes")) return "The accounting changes are measured, but the business causes are not established.";
  if (s.includes("modeled or synthetic cost components")) return "Some cost inputs are modeled rather than directly observed.";
  if (s.includes("no cross-domain joins, cohort comparisons, or statistical causal tests")) return "No linked-order or causal test connected finance and operations.";
  if (s.includes("only the supplied two periods") || s.includes("completeness across all dates")) return "Only the requested periods were checked; coverage across other dates was not confirmed.";
  if (s.includes("finance excludes certain orders") || s.includes("populations differ") || s.includes("cannot be silently equated")) return "Finance and operational measures may cover different orders.";
  if (s.includes("exact order-id audit") || s.includes("order id sets") || s.includes("order-id sets")) return "The exact orders included in each operational period have not been reconciled.";
  if (s.includes("metric-specific") || s.includes("denominator")) return "Metrics can use different eligible populations, so their counts may not match.";
  if (s.includes("modeled incident adjustments") || s.includes("modeled adjustments")) return "Some delivery or review values may include modeled adjustments.";
  if (s.includes("purchase-time cohorts") || s.includes("purchase-month")) return "Orders are grouped by purchase date; other event dates may differ.";
  if (s.includes("does not establish caus") || s.includes("no causal inference")) return "Observed changes do not establish what caused them.";
  if (s.includes("not a completed investigation") || s.includes("evidence plan")) return "This is an evidence plan, not a completed measurement.";
  if (s.includes("no data source was queried")) return "No source data was queried for this response.";
  if (s.includes("inventory") || s.includes("source recency") || s.includes("join permission")) return "The available evidence does not establish inventory, data freshness, or permission to link records.";
  return value;
}

function normalizedMeasure(id: string, source: JsonObject, status = str(source.status)): Measure {
  return { id, status, value: source.value, before: source.before, after: source.after, delta: source.delta,
    unit: str(source.unit) || str(obj(source.afterEvidence).unit) || str(obj(source.beforeEvidence).unit) || str(source.delta_unit),
    deltaUnit: str(source.delta_unit) || str(source.unit), period: source.period, population: obj(source.population),
    source: str(source.source), policy: str(source.policy), timeBasis: str(source.time_basis), limitations: strings(source.limitations),
    beforeEvidence: obj(source.beforeEvidence), afterEvidence: obj(source.afterEvidence), definition: str(source.definition) };
}

/** Maps established governed response variants to one presentation contract. It does not calculate or infer evidence. */
export function normalizeInvestigation(input: unknown): NormalizedInvestigation {
  const incoming = obj(input);
  const candidate = obj(incoming.canonical_result ?? incoming);
  const versioned = typeof candidate.schema_version === "string";
  const canonicalRecord: CanonicalInvestigation = versioned
    ? candidate as CanonicalInvestigation
    : { schema_version: INVESTIGATION_SCHEMA, question: str(incoming.question), payload: obj(incoming.result ?? incoming) };
  const r = obj(canonicalRecord.payload); const rawStatus = str(r.status).toUpperCase(); const route = str(r.route);
  const domainFinance = obj(obj(r.domain_results).finance);
  const financeResult = Object.keys(domainFinance).length ? domainFinance : r;
  const before = obj(r.before); const after = obj(r.after); const evidence = obj(r.evidence);
  const entries = evidenceEntries(canonicalRecord);
  const graphRows = arr(evidence.rows).map(obj);
  const observations = arr(r.observations).map(obj);
  const declared = obj(r.operational_changes ?? r.metric_changes);
  const measures: Measure[] = [];
  for (const [id, row] of Object.entries(declared)) {
    const metric = obj(row);
    measures.push(normalizedMeasure(id, { ...metric, source: metric.source ?? r.source, period: metric.period ?? r.periods, population: metric.population ?? r.population, policy: metric.policy ?? r.policy, time_basis: metric.time_basis ?? r.time_basis, limitations: metric.limitations ?? r.limitations }, str(metric.status) || rawStatus));
  }
  if (!measures.length && Object.keys(before).length && Object.keys(after).length) {
    measures.push(normalizedMeasure(str(r.metric_id) || str(before.metric_id) || "metric", { before: before.value, after: after.value, delta: r.delta, delta_unit: r.delta_unit, period: { before: before.period, after: after.period }, source: before.source, status: rawStatus, beforeEvidence: before, afterEvidence: after }));
  }
  if (!measures.length && Object.keys(obj(evidence.measurement)).length) {
    const current = obj(evidence.measurement); const previous = obj(evidence.before); const comparison = obj(evidence.comparison);
    measures.push(normalizedMeasure(str(evidence.metric_id) || str(current.metric_id), Object.keys(previous).length
      ? { before: previous.value, after: current.value, delta: comparison.absolute_change, delta_unit: comparison.change_unit,
          period: { before: previous.period, after: current.period }, source: current.source, beforeEvidence: previous, afterEvidence: current,
          limitations: mergeStrings(previous.limitations, current.limitations) }
      : current, str(current.status) || rawStatus));
  }
  // Accounting measurements retain separate before/after population proofs.
  for (const [id, item] of Object.entries(obj(financeResult.evidence))) {
    const pair = obj(item); const a = obj(pair.before); const b = obj(pair.after);
    const comparison = obj(obj(obj(financeResult.metric_results)[id]).comparison);
    if (Object.keys(a).length && Object.keys(b).length) measures.push(normalizedMeasure(id, {
      before: a.value, after: b.value, period: { before: a.period, after: b.period }, source: b.source,
      delta: comparison.absolute_change,
      unit: b.unit, beforeEvidence: a, afterEvidence: b, limitations: mergeStrings(a.limitations, b.limitations),
    }, str(b.status) || rawStatus));
  }
  if (!measures.length && Object.keys(evidence).length && !Array.isArray(evidence.rows)) measures.push(normalizedMeasure(str(evidence.metric_id) || str(r.metric_id) || "metric", evidence, str(evidence.status) || rawStatus));
  if (!measures.length) for (const row of observations) measures.push(normalizedMeasure(str(row.metric_id) || "metric", row, str(row.status) || rawStatus));
  if (!measures.length && Array.isArray(r.source_evidence)) for (const item of arr(r.source_evidence)) { const row = obj(item); measures.push(normalizedMeasure(str(row.metric_id) || "source evidence", row, str(row.status) || rawStatus)); }

  const finance = obj(r.financial_premise ?? r.premise);
  const evals = obj(financeResult.hypothesis_evaluation);
  const hypotheses = arr(r.accounting_hypotheses).length ? arr(r.accounting_hypotheses).map(obj) : arr(evals.hypotheses).map(obj);
  const accountingReconciliation = obj(r.accounting_reconciliation ?? r.accounting_reconciliation_check ?? r.reconciliation);
  const plan = obj(r.explanation_plan);
  const validExplanationCodes = new Set(["finance_divergence", "cost_per_order_context", "measured_metrics", "period_comparison", "product_gmv"]);
  const explanationPlan = plan.status === "VALIDATED" && typeof plan.explanation_type === "string" && validExplanationCodes.has(plan.explanation_type)
    && Array.isArray(plan.evidence_refs) && plan.evidence_refs.every((ref) => typeof ref === "string") ? plan : {};
  const intensity = obj(financeResult.order_normalized_evidence);
  const intensityComponents = arr(intensity.components).map(obj).filter((row) => typeof row.component === "string").map((row) => ({
    component: str(row.component), beforePerOrder: row.before_per_order, afterPerOrder: row.after_per_order, changePerOrder: row.change_per_order,
  }));
  const intensityCountsValid = typeof intensity.before_orders === "number" && Number.isInteger(intensity.before_orders) && intensity.before_orders > 0 && typeof intensity.after_orders === "number" && Number.isInteger(intensity.after_orders) && intensity.after_orders > 0;
  const intensityValuesValid = intensityComponents.length > 0 && intensityComponents.every((row) => {
    const beforeValue = numeric(row.beforePerOrder); const afterValue = numeric(row.afterPerOrder); const changeValue = numeric(row.changePerOrder);
    return beforeValue !== undefined && afterValue !== undefined && changeValue !== undefined
      && Math.abs((afterValue - beforeValue) - changeValue) <= 0.000001;
  });
  const perOrderCostEvidence = {
    status: str(intensity.status), populationBasis: str(intensity.population_basis),
    beforeOrders: Number.isInteger(intensity.before_orders) ? Number(intensity.before_orders) : undefined,
    afterOrders: Number.isInteger(intensity.after_orders) ? Number(intensity.after_orders) : undefined,
    components: intensityComponents, limitations: strings(intensity.limitations),
    validated: intensity.status === "RECONCILED_INTENSITY_COMPARISON" && intensity.causal_claim === false && intensityCountsValid && intensityValuesValid,
  };
  const requirements = mergeStrings(r.evidence_requirements);
  const causalClaim = typeof r.causal_claim === "boolean" ? r.causal_claim : null;
  const measuredStatuses = new Set(["MEASURED_WITH_LIMITATIONS", "PREMISE_NOT_CONFIRMED", "DESCRIPTIVE_DECOMPOSITION_ONLY", "PARTIAL_EVIDENCE_BUDGET", "INSUFFICIENT_GOVERNED_EVIDENCE", "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", "MEASURED_WITH_SCOPE_LIMITS", "CROSS_DOMAIN_DESCRIPTIVE_COMPARISON", "COMPARISON_MEASURED_WITH_SCOPE_LIMITS", "PARTIAL_GOVERNED_EVIDENCE", "EVIDENCE_RANKED_NOT_CAUSAL"]);
  const gapStatuses = new Set(["ACTIONABLE_EVIDENCE_GAP"]);
  const failedStatuses = new Set(["MULTIDOMAIN_NOT_VALIDATED", "INVESTIGATION_UNAVAILABLE", "EXECUTION_FAILED", "FAILED"]);
  let status: FindingStatus = "unverified";
  if (causalClaim === true) status = "unverified";
  else if (["NEEDS_CLARIFICATION", "NOT_INTERPRETED"].includes(rawStatus)) status = "clarification";
  else if (rawStatus === "NOT_YET_SUPPORTED") status = "unverified";
  else if (failedStatuses.has(rawStatus) || r.executable === false && !gapStatuses.has(rawStatus) && !requirements.length) status = "failed";
  else if (gapStatuses.has(rawStatus) || requirements.length > 0 && measures.length === 0) status = "evidence_gap";
  else if (measuredStatuses.has(rawStatus) && r.executable === true && (measures.length > 0 || graphRows.length > 0 || Object.keys(finance).length > 0 || hypotheses.length > 0)) status = "measured";
  if (versioned && candidate.schema_version !== INVESTIGATION_SCHEMA) status = "unverified";
  const coverage: EvidenceCoverage = status === "evidence_gap" ? "evidence_gap"
    : status === "clarification" ? "clarification"
      : status === "failed" ? "failed"
        : status === "unverified" ? "unsupported"
          : /PARTIAL|WITH_SCOPE_LIMITS|WITH_LIMITATIONS|INSUFFICIENT/i.test(rawStatus) || requirements.length > 0 || arr(r.limitations).length > 0 || arr(evals.limitations).length > 0 ? "partial" : "complete";

  const productContext = Object.keys(obj(evidence)).length ? evidence : r;
  const sourceEvidence = observations.length ? observations : Array.isArray(r.source_evidence) ? arr(r.source_evidence).map(obj) : Object.keys(evidence).length ? [evidence] : [];
  const implications = mergeStrings(r.business_implications, r.implications);
  return {
    canonicalRecord, evidenceEntries: entries, graphRows, accountingBridge: arr(financeResult.findings).map(obj),
    stopReasons: entries.filter((entry) => entry.path.endsWith("/stop_reason")),
    status, rawStatus: rawStatus || "UNVERIFIED", coverage, route, title: str(r.investigation_title) || route.replaceAll("_", " ") || "Investigation report",
    question: str(canonicalRecord.question) || str(r.question) || str(r.original_question) || str(obj(r.investigation_gateway).original_question),
    periods: obj(r.periods), domains: strings(r.domains ?? r.requested_domains), findings: mergeStrings(r.conclusions), measures,
    financialPremise: finance, accountingHypotheses: hypotheses, cohortEvidence: obj(r.operational_cohort_evidence),
    evidenceRequirements: requirements,
    nextValidations: mergeStrings(r.next_validations, r.next_validation ? [r.next_validation] : [], r.next_step ? [r.next_step] : [], ...hypotheses.map((h) => h.next_validation ? [h.next_validation] : [])),
    limitations: mergeStrings(r.limitations, evidence.limitations, financeResult.limitations, intensity.limitations, evals.limitations, ...observations.map((x) => x.limitations), ...measures.map((x) => x.limitations)),
    untestedHypotheses: obj(evals.untested ?? financeResult.hypotheses_not_tested), toolTrace: [...arr(r.tool_trace), ...arr(obj(financeResult.adaptive).trace), ...arr(r.execution_trace)].map(obj), causalClaim,
    reason: str(r.reason) || str(r.next_step), businessImplications: implications,
    productContext: obj(productContext), sourceEvidence, accountingReconciliation, perOrderCostEvidence, explanationPlan,
  };
}
