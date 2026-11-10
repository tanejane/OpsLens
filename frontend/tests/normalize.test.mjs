import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const source = await readFile(new URL("../lib/investigation.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const libUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
const lib = await import(libUrl);
const presentationSource = await readFile(new URL("../lib/report-presentation.ts", import.meta.url), "utf8");
const presentationCompiled = ts.transpileModule(presentationSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText.replace('from "./investigation"', `from "${libUrl}"`);
const presentationUrl = `data:text/javascript;base64,${Buffer.from(presentationCompiled).toString("base64")}`;
const presentation = await import(presentationUrl);
const dashboardSource = await readFile(new URL("../lib/dashboard.ts", import.meta.url), "utf8");
const dashboardCompiled = ts.transpileModule(dashboardSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const dashboard = await import(`data:text/javascript;base64,${Buffer.from(dashboardCompiled).toString("base64")}`);
const suggestionsSource = await readFile(new URL("../lib/suggestions.ts", import.meta.url), "utf8");
const suggestionsCompiled = ts.transpileModule(suggestionsSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const suggestions = await import(`data:text/javascript;base64,${Buffer.from(suggestionsCompiled).toString("base64")}`);
const apiClientSource = await readFile(new URL("../lib/api-client.ts", import.meta.url), "utf8");
const apiClientCompiled = ts.transpileModule(apiClientSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const apiClient = await import(`data:text/javascript;base64,${Buffer.from(apiClientCompiled).toString("base64")}`);
const pdfSource = await readFile(new URL("../lib/report-pdf.ts", import.meta.url), "utf8");
const pdfCompiled = ts.transpileModule(pdfSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText.replace('from "./investigation"', `from "${libUrl}"`).replace('from "./report-presentation"', `from "${presentationUrl}"`);
const pdf = await import(`data:text/javascript;base64,${Buffer.from(pdfCompiled).toString("base64")}`);
const fixtures = JSON.parse(await readFile(new URL("./fixtures/backend-results.json", import.meta.url), "utf8"));
const styles = await readFile(new URL("../app/styles.css", import.meta.url), "utf8");
function extractPdfText(source) { return [...source.matchAll(/\(((?:\\.|[^\\)])*)\) Tj/g)].map((match) => match[1].replace(/\\([\\()])/g, "$1")).join(" "); }
function extractPdfPages(source) { return [...source.matchAll(/stream\n([\s\S]*?)\nendstream/g)].filter((match) => /BT \/F[12]/.test(match[1])).map((match) => extractPdfText(match[1])); }

test("finance decomposition retains measured premise, accounting components and limits", () => {
  const result = lib.normalizeInvestigation(fixtures.finance_investigation);
  assert.equal(result.status, "measured");
  assert.equal(result.financialPremise.divergence_confirmed, true);
  assert.equal(result.accountingHypotheses.length, 5);
  assert.equal(result.causalClaim, false);
  assert.ok(result.limitations.some((item) => item.includes("causal root causes")));
  assert.equal(result.perOrderCostEvidence.validated, true);
  assert.equal(result.perOrderCostEvidence.beforeOrders, 6694);
  assert.equal(result.perOrderCostEvidence.afterOrders, 7188);
  assert.ok(result.perOrderCostEvidence.components.some((row) => row.component === "marketing_cost_effective"));
});

test("partial delivery and satisfaction observations retain denominator, source and eligibility details", () => {
  const result = lib.normalizeInvestigation(fixtures.delivery_review_partial);
  assert.equal(result.status, "measured");
  assert.equal(result.measures.length, 3);
  const delivery = result.measures.find((row) => row.id === "late_delivery_rate");
  assert.equal(delivery.population.lateness_eligible_orders, 6096);
  assert.equal(delivery.source, "semantic.order_delivery_evidence_v1");
  assert.equal(delivery.policy, "late_iff_actual_gt_estimated_on_eligible_orders");
  assert.equal(delivery.timeBasis, "order_purchase_time");
});

test("saved unsupported product request remains unverified", () => {
  const result = lib.normalizeInvestigation(fixtures.product_unsupported_saved);
  assert.equal(result.status, "unverified");
  assert.equal(result.measures.length, 0);
});

test("unsupported response stays an evidence gap without fabricating a measurement", () => {
  const result = lib.normalizeInvestigation(fixtures.unsupported_evidence_gap);
  assert.equal(result.status, "evidence_gap");
  assert.equal(result.measures.length, 0);
  assert.match(result.evidenceRequirements.join(" "), /seller and product linkage/);
  assert.equal(result.causalClaim, false);
});

test("clarification, unsupported causal request and execution error are distinct dispositions", () => {
  assert.equal(lib.normalizeInvestigation(fixtures.clarification).status, "clarification");
  assert.equal(lib.normalizeInvestigation(fixtures.unsupported_causal).status, "clarification");
  assert.equal(lib.normalizeInvestigation(fixtures.execution_error).status, "failed");
});

test("February–March evaluator metadata is not presented as a measured response payload", () => {
  const fixture = fixtures.feb_mar_three_domain_evaluation_record;
  assert.equal(fixture.response_payload_retained, false);
  assert.equal(fixture.case.passed, true);
  const result = lib.normalizeInvestigation(fixture.case);
  assert.equal(result.status, "unverified");
  assert.equal(result.measures.length, 0);
});

test("three-domain response schema from the governed backend normalizes all required sections", () => {
  const result = lib.normalizeInvestigation({ route: "three_domain_investigation", status: "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", executable: true, causal_claim: false, periods: { before: ["2018-02-01", "2018-03-01"], after: ["2018-03-01", "2018-04-01"] }, domains: ["finance", "delivery_operations", "customer_satisfaction"], financial_premise: { divergence_confirmed: true, revenue_delta: "139034.7300000042", contribution_profit_delta: "-48578.12892399993" }, accounting_hypotheses: [{ label: "Cost of goods sold", accounting_profit_impact: "99426.0906999986", source: "semantic.order_economics", causal_claim: false }], operational_changes: { late_delivery_rate: { before: "before-value", after: "after-value", delta: "delta-value", delta_unit: "percentage_points" }, average_review_score: { before: "before-value", after: "after-value", delta: "delta-value", delta_unit: "score_points" }, low_rating_rate: { before: "before-value", after: "after-value", delta: "delta-value", delta_unit: "percentage_points" } }, conclusions: ["Finance premise verified"], next_validations: ["Verify exact order-ID sets"], limitations: ["Descriptive only"], operational_cohort_evidence: { status: "NOT_ATTACHED", exact_order_id_sets_verified: false }, tool_trace: [{ capability: "governed_delivery_and_review_metrics" }] });
  assert.equal(result.status, "measured");
  assert.equal(result.measures.length, 3);
  assert.deepEqual(result.domains, ["finance", "delivery_operations", "customer_satisfaction"]);
  assert.equal(result.accountingHypotheses[0].source, "semantic.order_economics");
  assert.equal(result.cohortEvidence.exact_order_id_sets_verified, false);
});

test("causal claims fail closed even when a measured status is supplied", () => {
  const result = lib.normalizeInvestigation({ route: "three_domain_investigation", status: "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", executable: true, causal_claim: true, operational_changes: { late_delivery_rate: { before: 1, after: 2 } } });
  assert.equal(result.status, "unverified");
});

test("comparison measurements normalize into period aligned analyst measures", () => {
  const result = lib.normalizeInvestigation({ route: "investigation_planner", status: "COMPARISON_MEASURED_WITH_SCOPE_LIMITS", executable: true, causal_claim: false, metric_id: "average_review_score", before: { value: "before-value", period: ["2018-02-01", "2018-03-01"], population: { reviewed_orders: "denominator-token" }, source: "semantic.review" }, after: { value: "after-value", period: ["2018-03-01", "2018-04-01"] }, delta: "delta-token", delta_unit: "score_points" });
  assert.equal(result.status, "measured");
  assert.equal(result.measures[0].before, "before-value");
  assert.equal(result.measures[0].after, "after-value");
  assert.equal(result.measures[0].beforeEvidence.population.reviewed_orders, "denominator-token");
  assert.equal(result.measures[0].afterEvidence.population, undefined);
  assert.deepEqual(result.measures[0].population, {}); // No shared denominator was supplied.
});

test("dashboard investigation navigation carries the selected metric and exact compared months", () => {
  const question = dashboard.dashboardInvestigationQuestion("contribution_margin_pct", ["2018-05-01", "2018-06-01"], ["2018-06-01", "2018-07-01"]);
  assert.equal(question, "Compare contribution margin from May 2018 to June 2018");
});

test("each view has four supported suggested questions and selection only fills the composer", () => {
  assert.equal(suggestions.questionSuggestions.Business.length, 4);
  assert.equal(suggestions.questionSuggestions.Analyst.length, 4);
  const question = suggestions.questionSuggestions.Analyst[0].question;
  const filled = [];
  suggestions.selectSuggestedQuestion(question, (value) => filled.push(value));
  assert.deepEqual(filled, [question]);
});

test("API transport errors stay user friendly and do not echo upstream response bodies", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response("Internal Server Error: database password detail", { status: 500, headers: { "content-type": "text/plain" } });
  try {
    await assert.rejects(apiClient.requestJson("/api/dashboard"), (error) => {
      assert.match(error.message, /unreadable response/i);
      assert.doesNotMatch(error.message, /Internal Server Error|password detail/i);
      return true;
    });
  } finally { globalThis.fetch = originalFetch; }
});

test("business and analyst PDF exports are valid non-empty PDFs with facts and limitations", async () => {
  const report = lib.normalizeInvestigation(fixtures.finance_investigation);
  for (const mode of ["Business", "Analyst"]) {
    const blob = pdf.createInvestigationPdf(report, mode);
    const text = await blob.text();
    assert.equal(blob.type, "application/pdf");
    assert.ok(blob.size > 500);
    assert.ok(text.startsWith("%PDF-1.4"));
    assert.match(text, /xref/);
    const extracted = extractPdfText(text);
    assert.match(extracted, /Contribution profit/i);
    assert.match(extracted, /What Remains Unverified/i);
    assert.doesNotMatch(extracted, /Source: not returned|Population: not returned|\[object Object\]|\{"/i);
    assert.match(extracted, /caus/i);
    assert.match(extracted, /Direct answer/i);
    assert.match(extracted, /Generated/);
    assert.match(extracted, /currency/);
    assert.match(extracted, /139,034\.73/);
    assert.match(extracted, /-48,578\.13 currency units/);
    assert.match(extracted, /Revenue change: 139,034\.73 currency units/);
    assert.deepEqual(pdfRecord(text), report.canonicalRecord);
  }
});

test("three-domain and single-domain reports format titles, measures, audited evidence and provenance", async () => {
  for (const fixture of [fixtures.finance_investigation, fixtures.delivery_review_partial]) {
    const report = lib.normalizeInvestigation(fixture);
    for (const mode of ["Business", "Analyst"]) {
      const text = extractPdfText(await pdf.createInvestigationPdf(report, mode).text());
      assert.match(text, /Revenue increased|Late Delivery Rate/i);
      assert.match(text, /Finance changes|Measured results/);
      assert.doesNotMatch(text, /Source: not returned|not returned|\[object Object\]/i);
      if (fixture === fixtures.delivery_review_partial) assert.match(text, /2018-06-01/);
      if (mode === "Analyst" && fixture === fixtures.delivery_review_partial) {
        assert.match(text, /semantic\.order_delivery_evidence_v1/);
        assert.match(text, /6,167/);
        assert.match(text, /85/);
        const pages = extractPdfPages(await pdf.createInvestigationPdf(report, mode).text());
        assert.ok(pages.some((page) => page.includes("Low Rating Rate")));
        assert.match(text, /Source: semantic.order_review_evidence_v1/);
      }
    }
  }
});

test("three-domain PDF preserves the supplied finance, delivery, review and cohort audit values", async () => {
  // This response-shaped regression input is transcribed from the user-supplied OpsLens report PDF.
  const report = lib.normalizeInvestigation({
    route: "three_domain_investigation", investigation_title: "Three Domain Investigation", status: "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", executable: true, causal_claim: false,
    domains: ["finance", "delivery_operations", "customer_satisfaction"],
    periods: { before: ["2018-02-01", "2018-03-01"], after: ["2018-03-01", "2018-04-01"] },
    financial_premise: { revenue_delta: "139034.73", contribution_profit_delta: "-48578.13", divergence_confirmed: true },
    operational_changes: {
      late_delivery_rate: { before: "16", after: "21.36", delta: "5.36", delta_unit: "percentage_points" },
      average_review_score: { before: "3.83", after: "3.75", delta: "-0.07", delta_unit: "score_points" },
      low_rating_rate: { before: "20.74", after: "22.75", delta: "2", delta_unit: "percentage_points" },
    },
    accounting_hypotheses: [
      { label: "Cost of goods sold", accounting_profit_impact: "-99426.09", evidence_type: "reconciled_accounting_contribution", disposition: "supports_profit_pressure", source: "semantic.order_economics", causal_claim: false },
      { label: "Marketing expense", accounting_profit_impact: "-49291.24", evidence_type: "reconciled_accounting_contribution", disposition: "supports_profit_pressure", source: "semantic.order_cost_components", causal_claim: false },
      { label: "Refund expense", accounting_profit_impact: "-17118.93", evidence_type: "reconciled_accounting_contribution", disposition: "supports_profit_pressure", source: "semantic.order_cost_components", causal_claim: false },
      { label: "Campaign incentives", accounting_profit_impact: "-11541.68", evidence_type: "reconciled_accounting_contribution", disposition: "supports_profit_pressure", source: "semantic.order_cost_components", causal_claim: false },
      { label: "Fulfillment expense", accounting_profit_impact: "-7142.29", evidence_type: "reconciled_accounting_contribution", disposition: "supports_profit_pressure", source: "semantic.order_cost_components", causal_claim: false },
    ],
    operational_cohort_evidence: { status: "EXACT_ORDER_COHORT_RECONCILED", exact_order_id_sets_verified: true, limitation: "Does not validate equal finance order populations or equal metric-specific eligible subsets", months: [{ month: "2018-02-01", orders: 6728 }, { month: "2018-03-01", orders: 7211 }] },
    conclusions: ["Finance premise verified against its governed population", "Delivery and satisfaction changes are observed descriptively and do not explain profit causally"],
    next_validations: ["Verify operational mechanisms and cost allocation with separately approved linkage and confounder controls", "Validate modeled finance cost inputs against independent source records"],
    limitations: ["Finance excludes certain orders; operational populations differ", "Metric-specific delivery and review eligibility denominators differ", "Financial costs are modeled descriptive comparisons and do not prove causal impact"],
  });
  for (const mode of ["Business", "Analyst"]) {
    const source = await pdf.createInvestigationPdf(report, mode).text(); const text = extractPdfText(source);
    assert.match(text, /139,034\.73/); assert.match(text, /48,578\.13/); assert.match(text, /21\.36/); assert.match(text, /3\.75/);
    assert.match(text, /6,728/); assert.match(text, /7,211/); assert.match(text, /no causal|not establish|Descriptive/i);
    assert.doesNotMatch(text, /\[object Object\]|Source: not returned|\{"status"/i);
    assert.match(text, /Direct answer/i);
    assert.match(text, /percentage points/);
    assert.match(text, /score points/);
    assert.ok(text.indexOf("Direct answer") < text.indexOf("Measured results"));
    assert.match(text, /Recommended Next Validations/);
    assert.match(text, /Accounting Bridge/);
    assert.match(text, /What Remains Unverified/);
    const main = text.split("Evidence & Methodology")[0];
    assert.doesNotMatch(main, /SUPPORTS_PROFIT_PRESSURE|semantic\.order_economics|Verify attribution mechanism using independent operational data/i);
    assert.ok(text.indexOf("Cost of goods sold") < text.indexOf("Marketing expense"));
    assert.ok(text.indexOf("-99,426.09") < text.indexOf("-49,291.24"));
    if (mode === "Analyst") assert.match(text, /semantic\.order_cost_components/);
  }
});

test("shared report model ranks signed cost impacts and consolidates repeated accounting metadata", () => {
  const report = lib.normalizeInvestigation({
    status: "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", executable: true, causal_claim: false,
    financial_premise: { divergence_confirmed: true, revenue_delta: "139034.73", contribution_profit_delta: "-48578.13" },
    accounting_hypotheses: [
      { label: "Cost of goods sold", accounting_profit_impact: "-99426.0907", evidence_type: "reconciled_accounting_contribution", disposition: "SUPPORTS_PROFIT_PRESSURE", next_validation: "Verify attribution mechanism using independent operational data" },
      { label: "Marketing expense", accounting_profit_impact: "-49291.24", evidence_type: "reconciled_accounting_contribution", disposition: "SUPPORTS_PROFIT_PRESSURE", next_validation: "Verify attribution mechanism using independent operational data" },
      { label: "Refund expense", accounting_profit_impact: "-17118.93", evidence_type: "reconciled_accounting_contribution", disposition: "SUPPORTS_PROFIT_PRESSURE", next_validation: "Verify attribution mechanism using independent operational data" },
      { label: "Campaign incentives", accounting_profit_impact: "-11541.681294", evidence_type: "reconciled_accounting_contribution", disposition: "SUPPORTS_PROFIT_PRESSURE", next_validation: "Verify attribution mechanism using independent operational data" },
      { label: "Fulfillment expense", accounting_profit_impact: "-7142.2876", evidence_type: "reconciled_accounting_contribution", disposition: "SUPPORTS_PROFIT_PRESSURE", next_validation: "Verify attribution mechanism using independent operational data" },
    ], next_validations: ["Validate modeled finance cost inputs against independent source records", "Validate modeled finance cost inputs against independent source records"],
  });
  const model = presentation.buildReportPresentation(report);
  assert.match(model.answer, /Revenue increased while contribution profit declined/);
  assert.match(model.premise, /premise is confirmed/);
  assert.deepEqual(model.accounting.map((row) => row.impact), [-99426.0907, -49291.24, -17118.93, -11541.681294, -7142.2876]);
  assert.equal(model.accountingGroup.dispositions.length, 1);
  assert.equal(model.accountingGroup.evidenceTypes.length, 1);
  assert.equal(model.accountingGroup.validations.length, 1);
  assert.ok(model.validations.every((step, index) => model.validations.indexOf(step) === index));
  assert.ok(!model.validations.includes("Verify attribution mechanism using independent operational data"));
});

test("report presentation adapts to June delivery and review coverage without inventing a value for an evidence gap", () => {
  const june = presentation.buildReportPresentation(lib.normalizeInvestigation(fixtures.delivery_review_partial));
  assert.ok(june.metrics.some((metric) => metric.label === "Late Delivery Rate"));
  assert.ok(june.metrics.some((metric) => metric.label === "Average Review Score"));
  assert.ok(june.metrics.some((metric) => metric.label === "Low Rating Rate"));
  const unsupported = presentation.buildReportPresentation(lib.normalizeInvestigation(fixtures.unsupported_evidence_gap));
  assert.equal(unsupported.metrics.length, 0);
  assert.match(unsupported.answer, /does not support a measured answer/i);
  assert.ok(unsupported.evidenceNeeded.length > 0);
});

test("business presentation answers February–March finance divergence with ranked partial accounting pressures and a usable follow-up", () => {
  const finance = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(fixtures.finance_investigation));
  assert.match(finance.answer, /Revenue increased while contribution profit declined/);
  assert.match(finance.answer, /Cost of goods sold/);
  assert.equal(finance.accountingReconciled, false);
  assert.deepEqual(finance.accounting.slice(0, 2).map((row) => row.label), ["Cost of goods sold", "Marketing expense"]);
  assert.deepEqual(finance.accounting.slice(0, 2).map((row) => Number(row.impact.toFixed(2))), [-99426.09, -49291.24]);
  assert.ok(finance.findings.some((finding) => /partial/i.test(finding)));
  assert.equal(finance.availableFollowUps.length, 1);
  assert.match(finance.availableFollowUps[0], /February 2018 to March 2018/);
  assert.ok(finance.additionalEvidence.some((item) => /incremental campaign return/i.test(item)));
  assert.ok(finance.findings.every((finding) => !/SUPPORTS_PROFIT_PRESSURE|semantic\./i.test(finding)));
  assert.equal(finance.selectedAccounting.length, 3);
  assert.equal(finance.accounting.length, 5);
  assert.equal(finance.unreconciledAmount, undefined, "do not calculate a residual without validated comparable population, period and unit scopes");
  assert.match(finance.accountingSelectionNote, /3 of 5/);
  assert.match(finance.premise, /Population or coverage limits/);
  assert.deepEqual(finance.perOrderComponents.slice(0, 2).map((row) => row.label), ["Marketing expense", "Refund expense"]);
  assert.ok(finance.businessInterpretation.some((finding) => /no per-order COGS measure/i.test(finding)));
});

test("business presentation for a single delivery result and an evidence gap stays concise and does not invent values", () => {
  const delivery = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(fixtures.delivery_review_partial));
  assert.ok(delivery.metrics.some((metric) => metric.label === "Late Delivery Rate"));
  assert.ok(delivery.findings.length <= 3);
  const gap = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(fixtures.unsupported_evidence_gap));
  assert.equal(gap.metrics.length, 0);
  assert.equal(gap.availableFollowUps.length, 0);
  assert.match(gap.answer, /does not support a measured answer/i);
  assert.ok(gap.evidenceNeeded.length > 0);
  const causal = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(fixtures.unsupported_causal));
  assert.equal(causal.metrics.length, 0);
  assert.doesNotMatch(causal.answer, /caused by|because.*marketing/i);
  assert.equal(causal.coverage, "clarification");
  assert.equal(presentation.metricLabel("category_item_gmv"), "Category Item Gross Merchandise Value (GMV)");
  const unsupportedProduct = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(fixtures.product_unsupported_saved));
  assert.equal(unsupportedProduct.metrics.length, 0);
  assert.equal(unsupportedProduct.coverage, "unsupported");
});

test("supported cross-domain report keeps separate population limits and descriptive comparisons", () => {
  const report = lib.normalizeInvestigation({
    route: "three_domain_investigation", status: "THREE_DOMAIN_DESCRIPTIVE_EVIDENCE", executable: true, causal_claim: false,
    domains: ["finance", "delivery_operations", "customer_satisfaction"],
    periods: { before: ["2018-02-01", "2018-03-01"], after: ["2018-03-01", "2018-04-01"] },
    financial_premise: { revenue_delta: "139034.73", contribution_profit_delta: "-48578.13", divergence_confirmed: true },
    operational_changes: {
      late_delivery_rate: { before: "16", after: "21.36", delta: "5.36", delta_unit: "percentage_points" },
      average_review_score: { before: "3.83", after: "3.75", delta: "-0.08", delta_unit: "score_points" },
    },
    conclusions: ["Delivery and review populations have metric-specific eligibility and do not establish a cause of the finance movement."],
    limitations: ["Finance and operational populations differ", "Metric-specific denominators differ"],
  });
  const view = presentation.buildBusinessReportPresentation(report);
  assert.equal(view.coverage, "partial");
  assert.equal(view.metrics.length, 4);
  assert.match(view.answer, /2 operational measures were also returned/);
  assert.equal(view.availableFollowUps.length, 0);
  assert.ok(view.businessInterpretation.some((item) => /populations.*eligibility/i.test(item)));
  assert.equal(view.accountingReconciled, false);
});

test("accounting reconciliation is shown only when the response explicitly validates a comparable basis", () => {
  const input = {
    status: "EVIDENCE_RANKED_NOT_CAUSAL", executable: true, causal_claim: false,
    financial_premise: { revenue_delta: "8", contribution_profit_delta: "-30", divergence_confirmed: true },
    accounting_hypotheses: [
      { label: "Component A", accounting_profit_impact: "-10" },
      { label: "Component B", accounting_profit_impact: "-20" },
    ],
  };
  const unverified = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation(input));
  assert.equal(unverified.accountingReconciled, false, "matching arithmetic alone is insufficient");
  assert.equal(unverified.unreconciledAmount, undefined);
  const verified = presentation.buildBusinessReportPresentation(lib.normalizeInvestigation({
    ...input,
    accounting_reconciliation: { status: "RECONCILED", comparable: true, net_profit_change: "-30" },
  }));
  assert.equal(verified.accountingReconciled, true);
});

test("accounting pressure table has aligned desktop columns and compact responsive layouts", () => {
  assert.match(styles, /\.business-accounting-row\s*\{[^}]*grid-template-columns:\s*46px\s+minmax\(150px,1fr\)/s);
  assert.match(styles, /\.business-accounting-amount\s*\{[^}]*text-align:\s*right/s);
  assert.match(styles, /@media\s*\(max-width:\s*760px\)[\s\S]*?\.business-accounting-row/);
  assert.match(styles, /@media\s*\(max-width:\s*460px\)[\s\S]*?\.business-accounting-row/);
});

test("Gemini explanation plans can only select narratives backed by the canonical result", () => {
  const base = structuredClone(fixtures.finance_investigation);
  const componentRefs = base.order_normalized_evidence.components.map((row) => `order_normalized_evidence.components.${row.component}.change_per_order`);
  base.explanation_plan = { status: "VALIDATED", explanation_type: "cost_per_order_context", evidence_refs: ["order_normalized_evidence.status", ...componentRefs] };
  const report = lib.normalizeInvestigation(base);
  const view = presentation.buildBusinessReportPresentation(report);
  assert.match(view.businessInterpretation[0], /per-order comparison adds context/i);
  const invalid = lib.normalizeInvestigation({ ...base, explanation_plan: { status: "VALIDATED", explanation_type: "causal_marketing_failure", evidence_refs: ["made_up"] } });
  assert.equal(Object.keys(invalid.explanationPlan).length, 0);
  assert.match(presentation.buildBusinessReportPresentation(invalid).businessInterpretation.join(" "), /operating mechanisms/i);
});

test("per-order intensity is hidden when its returned delta fails numeric validation", () => {
  const tampered = structuredClone(fixtures.finance_investigation);
  tampered.order_normalized_evidence.components[0].change_per_order = "999";
  const report = lib.normalizeInvestigation(tampered);
  assert.equal(report.perOrderCostEvidence.validated, false);
  assert.equal(presentation.buildBusinessReportPresentation(report).perOrderComponents.length, 0);
});

test("evidence-gap PDF reports missing evidence without presenting empty measurements", async () => {
  const report = lib.normalizeInvestigation({ route: "investigation_planner", status: "ACTIONABLE_EVIDENCE_GAP", executable: false, requested_domains: ["finance"], question: "Why did this occur?", evidence_requirements: ["Independent campaign exposure and attribution evidence is required"], next_step: "Provide approved campaign evidence", causal_claim: false });
  for (const mode of ["Business", "Analyst"]) {
    const text = extractPdfText(await pdf.createInvestigationPdf(report, mode).text());
    assert.match(text, /Evidence gap/);
    assert.match(text, /Evidence Needed/);
    assert.match(text, /Independent campaign exposure/);
    assert.doesNotMatch(text, /Key Metrics|No measured finding is available.*0/);
  }
});

test("long analyst reports paginate with repeating page footers", async () => {
  const base = lib.normalizeInvestigation(fixtures.finance_investigation);
  const report = { ...base, limitations: Array.from({ length: 70 }, (_, i) => `Limitation ${i + 1}: ${"scope evidence boundary ".repeat(4)}`) };
  const text = await pdf.createInvestigationPdf(report, "Analyst").text();
  const pageObjects = [...text.matchAll(/\/Type \/Page\b/g)].length;
  assert.ok(pageObjects > 1);
  assert.match(extractPdfText(text), new RegExp(`${pageObjects} / ${pageObjects}`));
});

test("long accounting tables keep component rows together and repeat their header", async () => {
  const base = lib.normalizeInvestigation(fixtures.finance_investigation);
  const repeatedComponents = Array.from({ length: 18 }, (_, i) => ({ ...base.accountingHypotheses[i % base.accountingHypotheses.length], label: `Component ${i + 1}` }));
  const text = await pdf.createInvestigationPdf({ ...base, accountingHypotheses: repeatedComponents }, "Analyst").text();
  const pages = extractPdfPages(text);
  assert.ok(pages.length > 1);
  assert.ok(pages.filter((page) => page.includes("Cost component")).length > 1);
  assert.match(extractPdfText(text), new RegExp(`${pages.length} / ${pages.length}`));
});

// P0.2: unchanged captured responses and clearly labeled executor cases share
// the actual backend-generated API contract with both workspaces and PDF.
const p02 = JSON.parse(await readFile(new URL("./fixtures/p0_2_variants.json", import.meta.url), "utf8"));
const { createElement } = await import("react");
const { renderToStaticMarkup } = await import("react-dom/server");
const { createRequire } = await import("node:module");
const { pathToFileURL } = await import("node:url");
const require = createRequire(import.meta.url);
const evidenceComponentSource = await readFile(new URL("../components/investigation-evidence.tsx", import.meta.url), "utf8");
const evidenceComponentCompiled = ts.transpileModule(evidenceComponentSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText.replace('from "react/jsx-runtime"', `from "${pathToFileURL(require.resolve("react/jsx-runtime")).href}"`);
const { InvestigationEvidence } = await import(`data:text/javascript;base64,${Buffer.from(evidenceComponentCompiled).toString("base64")}`);
function pdfRecord(source) {
  assert.match(source, /\/EmbeddedFiles/);
  const match = source.match(/\/Type \/EmbeddedFile[^]*?stream\n([0-9a-f]+)>\nendstream/);
  assert.ok(match, "PDF contains exact JSON attachment");
  return JSON.parse(Buffer.from(match[1], "hex").toString("utf8"));
}
function htmlText(value) { return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#x27;"); }
for (const [name, fixture] of Object.entries(p02.cases)) {
  test(`P0.2 ${name}: API, normalization, both workspaces and both PDF attachments preserve every value`, async () => {
    const report = lib.normalizeInvestigation(fixture.api_response);
    assert.deepEqual(report.canonicalRecord.payload, fixture.result);
    assert.strictEqual(report.canonicalRecord, fixture.api_response.canonical_result);
    const entries = lib.evidenceEntries(report.canonicalRecord);
    assert.deepEqual(report.evidenceEntries, entries);
    for (const mode of ["Business", "Analyst"]) {
      const html = renderToStaticMarkup(createElement(InvestigationEvidence, { report, mode }));
      for (const entry of entries) {
        assert.ok(html.includes(htmlText(entry.path)), `${mode} lost path ${entry.path}`);
        assert.ok(html.includes(htmlText(entry.value)), `${mode} lost value at ${entry.path}`);
      }
      const source = await pdf.createInvestigationPdf(report, mode).text();
      assert.deepEqual(pdfRecord(source), report.canonicalRecord);
      // Readable pages are an answer-first summary. The decoded attachment above
      // preserves every original field, precision, unknown value and Unicode.
      const text = extractPdfText(source);
      assert.match(text, /Direct answer/i);
      assert.match(text, /opslens-investigation.json/);
      assert.doesNotMatch(text, /\[object Object\]/);

    }
  });
}

test("P0.2 variant projections retain nested measurements, graph rows, contradiction and adaptive trace", () => {
  const get = (key) => lib.normalizeInvestigation(p02.cases[key].api_response);
  const financial = get("financial");
  assert.equal(financial.measures[0].before, p02.cases.financial.result.evidence.before.value);
  assert.equal(financial.measures[0].after, p02.cases.financial.result.evidence.measurement.value);
  assert.deepEqual(financial.measures[0].afterEvidence, p02.cases.financial.result.evidence.measurement);
  const single = get("single_metric");
  assert.equal(single.measures[0].value, p02.cases.single_metric.result.evidence.value);
  const graph = get("graph");
  assert.equal(graph.status, "measured");
  assert.equal(graph.coverage, "partial");
  assert.deepEqual(graph.graphRows, p02.cases.graph.result.evidence.rows);
  assert.deepEqual(graph.limitations, p02.cases.graph.result.evidence.limitations);
  const adaptive = get("adaptive");
  assert.deepEqual(adaptive.toolTrace, p02.cases.adaptive.result.adaptive.trace);
  assert.equal(adaptive.accountingBridge.length, 3);
  assert.equal(adaptive.measures.length, 3);
  assert.equal(adaptive.perOrderCostEvidence.validated, true);
  const cross = get("cross_domain");
  assert.equal(cross.measures.length, 6);
  assert.deepEqual(cross.perOrderCostEvidence, adaptive.perOrderCostEvidence);
  assert.equal(cross.measures[0].beforeEvidence.population.eligible_orders, 6873);
  assert.equal(cross.measures[0].unit, "percent");
  assert.equal(cross.measures[0].deltaUnit, "percentage_points");
  assert.deepEqual(cross.measures[0].population, {});
  const contradiction = get("premise_contradiction");
  assert.equal(contradiction.status, "measured");
  assert.match(presentation.buildReportPresentation(contradiction).answer, /not confirmed/);
  assert.match(presentation.buildBusinessReportPresentation(contradiction).answer, /not confirmed/);
  assert.ok(contradiction.stopReasons.some((x) => x.value.includes("CLAIM_CONTRADICTED_BY_FINANCE")));
});

test("P0.2 unknown fields, IDs, Unicode, precision and unsupported versions survive without certification", async () => {
  const record = { schema_version: lib.INVESTIGATION_SCHEMA, question: "évidence", payload: { status: "FAILED", future: { evidence_id: "é/证据~1", figure: "12345678901234567890.123456789", limitations: ["Scope é: different denominator"], empty: [], missing: null, flag: false } } };
  const report = lib.normalizeInvestigation(record);
  assert.equal(report.status, "failed");
  for (const mode of ["Business", "Analyst"]) assert.deepEqual(pdfRecord(await pdf.createInvestigationPdf(report, mode).text()), record);
  const unknown = lib.normalizeInvestigation({ ...record, schema_version: "opslens.investigation.v999" });
  assert.equal(unknown.status, "unverified");
  assert.deepEqual(unknown.canonicalRecord.payload, record.payload);
});

test("P0.2 nested standalone measurement retains its original value and proof", async () => {
  const measurement = p02.cases.financial.result.evidence.measurement;
  const result = { route: "finance_measure", status: "MEASURED_WITH_SCOPE_LIMITS", executable: true, causal_claim: false, evidence: { metric_id: "effective_revenue", measurement } };
  const report = lib.normalizeInvestigation(result);
  assert.equal(report.status, "measured");
  assert.equal(report.measures[0].value, measurement.value);
  assert.equal(report.measures[0].source, measurement.source);
  assert.deepEqual(report.canonicalRecord.payload.evidence.measurement, measurement);
  assert.deepEqual(pdfRecord(await pdf.createInvestigationPdf(report, "Business").text()).payload, result);
});

test("P0.2 failed API response preserves completed evidence without becoming measured", async () => {
  const record = { schema_version: lib.INVESTIGATION_SCHEMA, question: "test failure", payload: { route: "investigation", status: "EXECUTION_FAILED", executable: false, causal_claim: false, validated_evidence: [{ producer: "synthetic-test-validator", result: p02.cases.single_metric.result.evidence }], limitations: ["Later execution failed; completed steps do not certify the full investigation"] } };
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: { reason: "Investigation could not complete", canonical_result: record } }), { status: 503, headers: { "content-type": "application/json" } });
    let caught;
    try { await apiClient.requestJson("/api/investigations"); } catch (error) { caught = error; }
    assert.ok(caught instanceof apiClient.ApiRequestError);
    assert.deepEqual(caught.canonicalResult, record);
    const report = lib.normalizeInvestigation(caught.canonicalResult);
    assert.equal(report.status, "failed");
    assert.equal(report.measures.length, 0);
    for (const mode of ["Business", "Analyst"]) {
      const html = renderToStaticMarkup(createElement(InvestigationEvidence, { report, mode }));
      assert.ok(html.includes("validated_evidence"));
      assert.deepEqual(pdfRecord(await pdf.createInvestigationPdf(report, mode).text()),record);
    }
  } finally { globalThis.fetch = originalFetch; }
});

test("P1.1 comparison evidence survives normalization and both PDF modes", async () => {
  const record = JSON.parse(await readFile(new URL("./fixtures/p1_1_comparison.json", import.meta.url), "utf8"));
  const report = lib.normalizeInvestigation(record);
  assert.deepEqual(report.canonicalRecord, record);
  for (const mode of ["Business", "Analyst"]) {
    const text = extractPdfText(await pdf.createInvestigationPdf(report, mode).text());
    assert.match(text, /Late versus on-time order ratings/);
    assert.match(text, /3.00/);
    assert.match(text, /4.00/);
    assert.match(text, /Descriptive association/);
  }
});

test("adaptive findings and traces survive both PDF modes", async () => {
  const cases=JSON.parse(await readFile(new URL('./fixtures/p1_2_adaptive.json',import.meta.url),'utf8'));
  for(const record of Object.values(cases)) {
    const report=lib.normalizeInvestigation(record);
    assert.deepEqual(report.canonicalRecord,record);
    for(const mode of ['Business','Analyst']) {
      const raw=await pdf.createInvestigationPdf(report,mode).text();
      assert.deepEqual(pdfRecord(raw),record);
      const text=extractPdfText(raw);
      assert.match(text,/Direct answer/i);
      assert.match(text,/execution traces/);
    }
  }
});

test('seller concentration preserves partitions and figures in both PDF modes',async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p1_3_seller.json',import.meta.url),'utf8'));
 const report=lib.normalizeInvestigation(record);assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst']){
  const text=extractPdfText(await pdf.createInvestigationPdf(report,mode).text());
  assert.match(text,/Seller concentration/);assert.match(text,/75.00/);assert.match(text,/Multi-seller orders/);
 }
});

test('document conflicts and passages survive normalization and PDF modes',async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_1_documents.json',import.meta.url),'utf8'));
 const report=lib.normalizeInvestigation(record);assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst']){
  const raw=await pdf.createInvestigationPdf(report,mode).text();
  assert.deepEqual(pdfRecord(raw),record);
  const text=extractPdfText(raw);
  assert.match(text,/Document cross-check/);assert.match(text,/CONTRADICTS/);assert.match(text,/CORROBORATES/);
  assert.match(text,/embedded canonical JSON attachment/);
  assert.doesNotMatch(text,/evidence appendix/);
 }
});

test('captured live document follow-up preserves every canonical field in both PDF attachments',async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_1_live_documents.json',import.meta.url),'utf8'));
 const report=lib.normalizeInvestigation(record);
 assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst']){
  const raw=await pdf.createInvestigationPdf(report,mode).text();
  assert.deepEqual(pdfRecord(raw),record);
  const text=extractPdfText(raw);
  assert.match(text,/growthmax_campaign_brief/);
  assert.match(text,/Document cross-check/);
 }
});

test('observability metadata survives normalization and PDF replay record',async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_1_live_documents.json',import.meta.url),'utf8'));
 record.payload.observability={run_id:'trace-fixture',evidence:[{evidence_id:'hash-fixture'}],latency_ms:123,stop_reason:'ASSESSED'};
 const report=lib.normalizeInvestigation(record);
 assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst'])assert.deepEqual(pdfRecord(await pdf.createInvestigationPdf(report,mode).text()),record);
});

test('refund amounts, denominators and trace survive both PDF modes exactly',async()=>{
 const record=JSON.parse(await readFile(new URL('./fixtures/p2_3_refunds.json',import.meta.url),'utf8'));
 const report=lib.normalizeInvestigation(record);assert.deepEqual(report.canonicalRecord,record);
 for(const mode of ['Business','Analyst']){
  const raw=await pdf.createInvestigationPdf(report,mode).text();
  assert.deepEqual(pdfRecord(raw),record);
  const text=extractPdfText(raw);assert.match(text,/Order-linked refund concentration/);assert.match(text,/30.50/);
 }
});
