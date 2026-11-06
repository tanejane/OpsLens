import type { JsonObject, NormalizedInvestigation } from "./investigation";

export type AccountingRow = { label: string; impact: number; source?: string };
export type AccountingGroup = {
  evidenceTypes: string[]; dispositions: string[]; causalClaims: string[];
  validations: string[]; sources: string[];
};
export type ReportPresentation = {
  answer: string; premise: string; metrics: { label: string; before?: unknown; after?: unknown; delta?: unknown; unit?: string; deltaUnit?: string; value?: unknown }[];
  accounting: AccountingRow[]; accountingGroup: AccountingGroup; findings: string[];
  limitations: string[]; validations: string[]; evidenceNeeded: string[];
  accountingReconciled: boolean; shownAccountingImpact: number; netProfitChange?: number;
  availableFollowUps: string[]; additionalEvidence: string[];
};
export type BusinessReportPresentation = {
  answer: string; premise: string; coverage: NormalizedInvestigation["coverage"];
  metrics: { label: string; before?: unknown; after?: unknown; delta?: unknown; unit?: string; deltaUnit?: string; value?: unknown }[];
  accounting: AccountingRow[]; selectedAccounting: AccountingRow[]; accountingSelectionNote: string;
  accountingGroup: AccountingGroup; accountingComparable: boolean; accountingReconciled: boolean; unreconciledAmount?: number;
  perOrderCostEvidence: NormalizedInvestigation["perOrderCostEvidence"];
  perOrderComponents: { label: string; before: number; after: number; change: number }[];
  findings: string[]; businessInterpretation: string[]; limitations: string[];
  validations: string[]; evidenceNeeded: string[]; availableFollowUps: string[]; additionalEvidence: string[];
};

const text = (value: unknown) => typeof value === "string" ? value.trim() : "";
const number = (value: unknown): number | undefined => {
  if (typeof value !== "number" && typeof value !== "string") return undefined;
  if (typeof value === "string" && value.trim() === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};
const unique = (values: string[]) => [...new Map(values.map((v) => v.trim()).filter(Boolean).map((v) => [v.toLocaleLowerCase(), v.trim()])).values()];
const human = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const normalizeList = (value: unknown) => Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
const metricNames: Record<string, string> = {
  late_delivery_rate: "Late Delivery Rate", average_review_score: "Average Review Score", low_rating_rate: "Low Rating Rate",
  review_coverage: "Review Coverage", purchase_session_rate: "Purchase Session Rate", checkout_abandon_rate: "Checkout Abandonment Rate",
  orders: "Orders", revenue: "Revenue", contribution_profit: "Contribution Profit", contribution_margin: "Contribution Margin",
  category_item_gmv: "Category Item Gross Merchandise Value (GMV)", total_item_gmv: "Total Item Gross Merchandise Value (GMV)",
};
export function metricLabel(id: string): string { return metricNames[id.toLowerCase()] ?? human(id); }
function costComponentLabel(id: string): string {
  const names: Record<string, string> = {
    refund_amount: "Refund expense", fulfillment_cost: "Fulfillment expense", payment_processing_cost: "Payment processing cost",
    marketing_cost_effective: "Marketing expense", incentive_cost_effective: "Campaign incentives", effective_cogs: "Cost of goods sold",
    other_adjustments_residual: "Other adjustments residual",
  };
  return names[id] ?? human(id);
}

/** Accounting impacts are ranked by absolute magnitude so favorable offsets remain visible in their true sign. */
export function rankAccountingRows(rows: JsonObject[]): AccountingRow[] {
  return rows.map((row) => ({
    label: text(row.label) || human(text(row.hypothesis_id) || "Accounting component"),
    impact: number(row.accounting_profit_impact) ?? Number.NaN,
    source: text(row.source) || undefined,
  })).filter((row) => Number.isFinite(row.impact))
    .sort((a, b) => a.impact - b.impact);
}

function rankBusinessAccountingRows(rows: JsonObject[]): AccountingRow[] {
  return rankAccountingRows(rows).sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact));
}

function uniqueValidations(report: NormalizedInvestigation): string[] {
  return unique(normalizeList(report.nextValidations)).filter((v) => !/^(?:verify attribution mechanism using independent operational data|require independently approved order\/seller\/carrier linkage to evaluate concentration or attribution)\.?$/i.test(v.trim()));
}
function month(value: unknown): string {
  if (!Array.isArray(value)) return "";
  const match = /^(\d{4})-(\d{2})/.exec(String(value[0] ?? ""));
  return match ? `${new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1)).toLocaleString("en", { month: "long", timeZone: "UTC" })} ${match[1]}` : "";
}
function periodText(value: unknown): string {
  if (!Array.isArray(value)) return text(value);
  const start = String(value[0] ?? "");
  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(start);
  return match ? `${new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1)).toLocaleString("en", { month: "long", timeZone: "UTC" })} ${match[1]}` : start;
}
function numberText(value: unknown): string {
  const parsed = number(value);
  return parsed === undefined ? "" : parsed.toLocaleString("en", { maximumFractionDigits: 2 });
}
function cleanNarrative(value: string): boolean {
  return !/\b(?:semantic\.[a-z0-9_.]+|SUPPORTS_PROFIT_PRESSURE|reconciled_accounting_contribution|evidence_type|next_validation|causal root cause|no causal inference)\b/i.test(value);
}
function prioritizeEvidence(items: string[], question: string): string[] {
  const stop = new Set(["about", "after", "before", "from", "into", "that", "this", "what", "when", "where", "which", "with", "were", "does", "did", "the", "and", "for", "was", "are", "how", "why", "compare", "show", "tell"]);
  const tokens = question.toLowerCase().match(/[a-z0-9]+/g)?.filter((word) => word.length > 2 && !stop.has(word)) ?? [];
  return items.map((value, index) => ({ value, index, score: tokens.reduce((sum, token) => sum + (value.toLowerCase().includes(token) ? 1 : 0), 0) }))
    .sort((a, b) => b.score - a.score || a.index - b.index).map((item) => item.value);
}
function verifiedExplanationType(report: NormalizedInvestigation): string {
  const plan = report.explanationPlan;
  if (plan.status !== "VALIDATED" || typeof plan.explanation_type !== "string" || !Array.isArray(plan.evidence_refs)) return "";
  const refs = plan.evidence_refs.filter((value): value is string => typeof value === "string");
  const hasRefs = (...required: string[]) => required.every((ref) => refs.includes(ref));
  const exactRefs = (required: string[]) => refs.length === required.length && required.every((ref) => refs.includes(ref));
  const code = plan.explanation_type;
  if (code === "finance_divergence" && report.financialPremise.divergence_confirmed === true
    && number(report.financialPremise.revenue_delta) !== undefined && number(report.financialPremise.contribution_profit_delta) !== undefined
    && hasRefs("premise.divergence_confirmed", "premise.revenue_delta", "premise.contribution_profit_delta")) return code;
  if (code === "cost_per_order_context" && report.perOrderCostEvidence.validated
    && hasRefs("order_normalized_evidence.status", ...report.perOrderCostEvidence.components.map((component) => `order_normalized_evidence.components.${component.component}.change_per_order`))) return code;
  if (code === "measured_metrics") {
    const expected = report.sourceEvidence.flatMap((row, index) => row.causal_claim === false
      && typeof row.metric_id === "string" && number(row.value) !== undefined
      ? [`observations.${index}.metric_id`, `observations.${index}.value`] : []);
    if (expected.length > 0 && exactRefs(expected)) return code;
  }
  if (code === "period_comparison") {
    const prefix = refs.some((ref) => ref.startsWith("metric_changes.")) ? "metric_changes" : "operational_changes";
    const expected = report.measures.flatMap((measure) => measure.before !== undefined && measure.after !== undefined && measure.delta !== undefined
      ? ["before", "after", "delta"].map((field) => `${prefix}.${measure.id}.${field}`) : []);
    if (expected.length > 0 && exactRefs(expected)) return code;
  }
  if (code === "product_gmv" && report.productContext.status === "MEASURED_WITH_SCOPE_LIMITS" && report.productContext.causal_claim === false
    && /gmv/i.test(text(report.productContext.metric_id)) && number(report.productContext.value) !== undefined
    && hasRefs("evidence.metric_id", "evidence.value", "evidence.category", "evidence.period", "evidence.source")) return code;
  return "";
}

/** Existing Analyst/PDF adapter. Business-specific narration stays in a separate adapter. */
export function buildReportPresentation(report: NormalizedInvestigation): ReportPresentation {
  const financial = report.financialPremise;
  const divergence = financial.divergence_confirmed === true;
  const accounting = rankAccountingRows(report.accountingHypotheses);
  const accountingGroup: AccountingGroup = {
    evidenceTypes: unique(report.accountingHypotheses.map((h) => human(text(h.evidence_type)))),
    dispositions: unique(report.accountingHypotheses.map((h) => human(text(h.disposition)))),
    causalClaims: unique(report.accountingHypotheses.map((h) => typeof h.causal_claim === "boolean" ? (h.causal_claim ? "Causal claim asserted" : "Non-causal accounting contribution") : "")),
    validations: unique(report.accountingHypotheses.map((h) => text(h.next_validation))),
    sources: unique(report.accountingHypotheses.map((h) => text(h.source))),
  };
  const metrics: ReportPresentation["metrics"] = report.measures.map((m) => ({ label: human(m.id), before: m.before, after: m.after, delta: m.delta, unit: m.unit, deltaUnit: m.deltaUnit, value: m.value }));
  if (financial.revenue_delta !== undefined) metrics.unshift({ label: "Revenue change", delta: financial.revenue_delta, unit: "currency" });
  if (financial.contribution_profit_delta !== undefined) metrics.splice(1, 0, { label: "Contribution profit change", delta: financial.contribution_profit_delta, unit: "currency" });
  const answer = report.status !== "measured"
    ? report.status === "evidence_gap" ? "The available evidence does not support a measured answer yet."
      : report.status === "clarification" ? "More detail is needed before this question can be investigated."
        : report.status === "failed" ? "The investigation could not be completed; no finding is presented as measured."
          : "This result has not been verified against the evidence contract."
    : financial.divergence_confirmed === false ? "The revenue-up/profit-down premise was not confirmed by the governed measurements."
    : divergence ? "Revenue increased while contribution profit declined across the compared periods."
      : report.findings[0] || "The requested metrics were measured for the specified scope.";
  const premise = divergence ? "The revenue-up/profit-down premise is confirmed in the governed finance comparison. This verifies the movement, not its cause."
    : report.status === "measured" ? "The comparison reflects the supplied governed measurements; no causal conclusion is implied."
      : report.reason || "No verified premise is available.";
  const netProfitChange = Number(financial.contribution_profit_delta);
  const shownAccountingImpact = accounting.reduce((sum, row) => sum + row.impact, 0);
  const accountingReconciled = Number.isFinite(netProfitChange) && accounting.length > 0 && Math.abs(shownAccountingImpact - netProfitChange) <= 0.01;
  const beforeMonth = month(report.periods.before);
  const afterMonth = month(report.periods.after);
  const hasOperationalComparison = report.domains.some((domain) => /delivery|satisfaction|review/i.test(domain));
  const availableFollowUps = divergence && beforeMonth && afterMonth && !hasOperationalComparison
    ? [`Compare finance, late delivery and review scores from ${beforeMonth} to ${afterMonth}`]
    : [];
  const additionalEvidence = unique([
    ...report.nextValidations.filter((value) => !availableFollowUps.includes(value)),
    ...Object.values(report.untestedHypotheses).filter((value): value is string => typeof value === "string"),
  ]);
  const shortLimitations = unique(report.limitations);
  const businessFindings = divergence && accounting.length > 0
    ? [
        `${accounting[0].label} is the largest returned downward profit contribution (${accounting[0].impact.toLocaleString("en", { maximumFractionDigits: 2 })} in reported units).`,
        ...(accounting[1] ? [`${accounting[1].label} is the second-largest returned pressure (${accounting[1].impact.toLocaleString("en", { maximumFractionDigits: 2 })} in reported units).`] : []),
        ...(!accountingReconciled ? ["The returned components do not reconcile to the full net profit movement; this breakdown is partial."] : []),
      ]
    : [];
  return {
    answer, premise, metrics, accounting, accountingGroup,
    findings: businessFindings.length ? businessFindings : unique([...report.businessImplications, ...report.findings].filter((v) => !/\b(?:semantic\.[a-z0-9_.]+|SUPPORTS_PROFIT_PRESSURE|reconciled_accounting_contribution|evidence_type|next_validation)\b/i.test(v))).slice(0, 3),
    limitations: shortLimitations, validations: uniqueValidations(report), evidenceNeeded: unique(report.evidenceRequirements),
    accountingReconciled, shownAccountingImpact, netProfitChange: Number.isFinite(netProfitChange) ? netProfitChange : undefined,
    availableFollowUps, additionalEvidence,
  };
}

export function buildBusinessReportPresentation(report: NormalizedInvestigation): BusinessReportPresentation {
  const financial = report.financialPremise;
  const divergence = financial.divergence_confirmed === true;
  const accounting = rankBusinessAccountingRows(report.accountingHypotheses);
  const selectedAccounting = accounting.slice(0, 3);
  const perOrderComponents = report.perOrderCostEvidence.validated
    ? report.perOrderCostEvidence.components.map((component) => ({
        label: costComponentLabel(component.component), before: number(component.beforePerOrder)!,
        after: number(component.afterPerOrder)!, change: number(component.changePerOrder)!,
      })).sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
    : [];
  const accountingGroup: AccountingGroup = {
    evidenceTypes: unique(report.accountingHypotheses.map((h) => human(text(h.evidence_type)))),
    dispositions: unique(report.accountingHypotheses.map((h) => human(text(h.disposition)))),
    causalClaims: unique(report.accountingHypotheses.map((h) => typeof h.causal_claim === "boolean" ? (h.causal_claim ? "Causal claim asserted" : "Non-causal accounting contribution") : "")),
    validations: unique(report.accountingHypotheses.map((h) => text(h.next_validation))),
    sources: unique(report.accountingHypotheses.map((h) => text(h.source))),
  };
  const metrics: BusinessReportPresentation["metrics"] = report.measures.map((m) => ({ label: metricLabel(m.id), before: m.before, after: m.after, delta: m.delta, unit: m.unit, deltaUnit: m.deltaUnit, value: m.value }));
  if (financial.revenue_delta !== undefined) metrics.unshift({ label: "Revenue change", delta: financial.revenue_delta, unit: "reported units" });
  if (financial.contribution_profit_delta !== undefined) metrics.splice(1, 0, { label: "Contribution profit change", delta: financial.contribution_profit_delta, unit: "reported units" });

  const reconciliation = report.accountingReconciliation;
  const explicitlyComparable = reconciliation.comparable === true || reconciliation.same_population === true && reconciliation.same_periods === true && reconciliation.same_unit === true;
  const explicitlyReconciled = reconciliation.reconciled === true || text(reconciliation.status).toUpperCase() === "RECONCILED";
  const netProfitChange = number(reconciliation.net_profit_change) ?? number(financial.contribution_profit_delta);
  const componentTotal = accounting.reduce((sum, row) => sum + row.impact, 0);
  const arithmeticDifference = netProfitChange === undefined ? undefined : netProfitChange - componentTotal;
  const accountingReconciled = explicitlyComparable && explicitlyReconciled && arithmeticDifference !== undefined && Math.abs(arithmeticDifference) <= 0.01;
  const unreconciledAmount = explicitlyComparable && arithmeticDifference !== undefined && Math.abs(arithmeticDifference) > 0.01 ? arithmeticDifference : undefined;

  const operationalFacts = report.measures.flatMap((measure) => {
    const name = metricLabel(measure.id);
    const delta = numberText(measure.delta);
    if (measure.before !== undefined && measure.after !== undefined) {
      const unit = measure.unit ? ` ${measure.unit.replaceAll("_", " ")}` : "";
      const deltaUnit = measure.deltaUnit ? ` ${measure.deltaUnit.replaceAll("_", " ")}` : unit;
      const movement = delta ? ` (reported change ${delta}${deltaUnit})` : "";
      return [`${name}: ${numberText(measure.before)} to ${numberText(measure.after)}${unit}${movement}.`];
    }
    if (measure.value !== undefined && numberText(measure.value)) {
      const unit = measure.unit ? ` ${measure.unit.replaceAll("_", " ")}` : "";
      const when = periodText(measure.period);
      return [`${name} measured ${numberText(measure.value)}${unit}${when ? ` for ${when}` : ""}.`];
    }
    return [];
  });
  const implications = unique([...report.businessImplications, ...report.findings].filter(cleanNarrative));
  const accountingFindings = selectedAccounting.map((row) => `${row.label} recorded ${row.impact < 0 ? "a downward" : row.impact > 0 ? "an upward" : "no net"} contribution to profit (${numberText(row.impact)} reported units). This is an accounting movement, not an established operating cause.`);

  const product = report.productContext;
  const category = text(product.category);
  const categoryGmv = number(product.category_item_gmv);
  const totalGmv = number(product.total_item_gmv);
  const productFacts = category && categoryGmv !== undefined
    ? [`${human(category)} category item gross merchandise value (GMV) was ${numberText(categoryGmv)}${totalGmv !== undefined ? `; total item GMV was ${numberText(totalGmv)}` : ""}.`]
    : [];
  const generatedFacts = unique([...operationalFacts, ...accountingFindings]);
  const hasOperations = report.domains.some((domain) => /delivery|satisfaction|review/i.test(domain)) || report.measures.some((m) => /delivery|review|rating/i.test(m.id));

  let answer: string;
  if (report.status === "evidence_gap") answer = "The current evidence does not support a measured answer to this question.";
  else if (report.status === "clarification") answer = report.reason || "Please clarify the metric or comparison period so the investigation can run.";
  else if (report.status === "failed") answer = "The investigation could not complete, so no finding is presented as measured.";
  else if (report.status !== "measured") answer = report.reason || "This result has not been verified against the evidence contract.";
  else if (financial.divergence_confirmed === false) answer = "The revenue-up/profit-down premise was not confirmed by the governed measurements.";
  else if (divergence && selectedAccounting.length) answer = `Revenue increased while contribution profit declined. The largest returned accounting movement was ${selectedAccounting[0].label} (${numberText(selectedAccounting[0].impact)} reported units); this identifies a recorded profit contribution, not its operating cause.`;
  else if (divergence && hasOperations && operationalFacts.length) answer = `Revenue increased while contribution profit declined; ${operationalFacts.length} operational measures were also returned for descriptive comparison. These results do not identify a cause.`;
  else if (productFacts.length) answer = productFacts[0];
  else if (divergence) answer = "Revenue increased while contribution profit declined across the compared periods.";
  else if (operationalFacts.length === 1) answer = operationalFacts[0];
  else if (operationalFacts.length > 1) answer = `${operationalFacts.length} requested measures were returned for the stated scope; the comparisons are descriptive.`;
  else answer = implications[0] || "Validated measurements are available for the requested scope.";

  const premise = report.status === "measured"
      ? divergence ? `The supplied finance comparison confirms the revenue-up/profit-down movement; it does not establish an operational cause.${report.coverage === "partial" ? " Population or coverage limits apply as noted below." : ""}`
      : report.coverage === "partial" ? "Measurements are available, with the scope limits below. No causal conclusion is implied."
        : "The result reflects the returned governed measurements. No causal conclusion is implied."
    : report.status === "evidence_gap" ? ""
      : report.reason && report.reason !== answer ? report.reason : "";

  const beforeMonth = month(report.periods.before);
  const afterMonth = month(report.periods.after);
  const hasFinance = report.domains.some((domain) => /finance/i.test(domain)) || Object.keys(financial).length > 0;
  const availableFollowUps = report.status === "measured" && hasFinance && !hasOperations && beforeMonth && afterMonth
    ? [`Compare finance, late delivery and review scores from ${beforeMonth} to ${afterMonth}`]
    : [];
  const additionalEvidence = prioritizeEvidence(unique([
    ...report.evidenceRequirements,
    ...uniqueValidations(report),
    ...Object.values(report.untestedHypotheses).filter((value): value is string => typeof value === "string"),
  ]).filter(cleanNarrative), report.question);
  const deterministicInterpretation = report.status === "measured"
    ? divergence && hasOperations
      ? ["Delivery and review movements were measured alongside finance, but those comparisons do not establish that either operational movement caused the profit decline."]
      : divergence
        ? ["Revenue growth did not translate into contribution-profit growth in these periods. The component list records accounting pressures; it does not identify the operating mechanisms behind them.", ...(perOrderComponents.length && accounting.some((row) => /cost of goods sold/i.test(row.label)) && !perOrderComponents.some((row) => /cost of goods sold/i.test(row.label)) ? ["Cost of goods sold is the largest returned total pressure, but no per-order COGS measure was returned to distinguish total movement from per-order movement."] : [])]
        : productFacts.length
          ? ["GMV is a merchandise sales-value measure; it should not be read as contribution profit."]
          : report.measures.length > 0 && report.measures.every((measure) => measure.before === undefined && measure.after === undefined)
            ? ["The result is a measured value for the requested period; no prior-period comparison was returned, so a trend cannot be inferred."]
            : []
    : [];
  const planType = verifiedExplanationType(report);
  const planInterpretation: Record<string, string> = {
    finance_divergence: "Revenue and contribution profit moved in opposite directions; the returned accounting measurements describe where profit pressure was recorded, not the operating cause.",
    cost_per_order_context: "The per-order comparison adds context to total cost movements, but these are cohort averages and do not prove what caused costs to change.",
    measured_metrics: "This explanation uses only the metric values returned for the requested period; no additional cause is inferred.",
    period_comparison: "The period comparisons show co-occurring movements; they do not establish that one measure caused another.",
    product_gmv: "The category GMV value describes item sales value, not contribution profit.",
  };
  const usefulImplications = implications.filter((line) => !generatedFacts.includes(line) && !/descriptiv|causal|premise verified|evidence gap/i.test(line));
  const businessInterpretation = unique([planInterpretation[planType] ?? "", ...deterministicInterpretation, ...usefulImplications]).slice(0, 3);
  const findings = accounting.length > 0 && !accountingReconciled
    ? unique([...operationalFacts, ...accountingFindings.slice(0, 2), "The returned component list is partial; a complete, like-for-like bridge to the net profit movement is not certified."]).slice(0, 3)
    : unique(generatedFacts).slice(0, 3);
  const limitations = unique(report.limitations.filter((line) => /population|eligib|modeled|synthetic|coverage|period|causal|denominator/i.test(line)).map((line) => line)).slice(0, 2);

  return {
    answer, premise, coverage: report.coverage,
    metrics, accounting, selectedAccounting,
    accountingSelectionNote: accounting.length ? `Showing ${selectedAccounting.length} of ${accounting.length} returned components, ranked by absolute recorded profit impact. Positive values increased profit; negative values reduced it.` : "",
    accountingGroup, accountingComparable: explicitlyComparable, accountingReconciled, unreconciledAmount,
    perOrderCostEvidence: report.perOrderCostEvidence, perOrderComponents,
    findings, businessInterpretation, limitations, validations: uniqueValidations(report), evidenceNeeded: unique(report.evidenceRequirements),
    availableFollowUps, additionalEvidence,
  };
}

export function evidenceSummary(group: AccountingGroup): string[] {
  return [
    ...group.evidenceTypes.map((v) => `Evidence type: ${v}`),
    ...group.dispositions.map((v) => `Disposition: ${v}`),
    ...group.causalClaims.map((v) => `Causal status: ${v}`),
    ...group.validations.map((v) => `Accounting validation: ${v}`),
    ...group.sources.map((v) => `Source: ${v}`),
  ];
}
