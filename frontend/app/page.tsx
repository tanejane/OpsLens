
"use client";

import { useEffect, useState } from "react";
import { BusinessLanding } from "../components/business-landing";
import { BusinessDashboard } from "../components/BusinessDashboard";
import { PageHeading, SectionHeading } from "../components/ui";
import { InvestigationEvidence } from "../components/investigation-evidence";
import { DocumentEvidence } from "../components/document-evidence";
import { InvestigationTimeline } from "../components/investigation-timeline";
import { RefundConcentration } from "../components/refund-concentration";
import { DeliveryReviewComparison } from "../components/delivery-review-comparison";
import { SellerConcentration } from "../components/seller-concentration";
import {
  normalizeInvestigation,
  plainLanguageLimitation,
  type NormalizedInvestigation,
} from "../lib/investigation";
import { createInvestigationPdf } from "../lib/report-pdf";
import {
  buildBusinessReportPresentation,
  buildReportPresentation,
  evidenceSummary,
  metricLabel,
  rankAccountingRows,
} from "../lib/report-presentation";
import { InvestigationSessionClient } from "../lib/investigation-session";
import { requestJson, ApiRequestError } from "../lib/api-client";
import { questionSuggestions, selectSuggestedQuestion } from "../lib/suggestions";
import {
  ArrowRight,
  Download,
  ChevronDown,
  CircleHelp,
  FileSearch2,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Search,
  ShieldCheck,
} from "lucide-react";

type PageName = "Home" | "Investigations" | "Reports";
type Data = Record<string, unknown>;
type ReportMode = "Business" | "Analyst";

type BusinessReasoning = {
  status: "UNVERIFIED_ANALYSIS";
  business_significance: string[];
  possible_explanations: string[];
  recommended_checks: string[];
  maintenance_actions: string[];
  caveat: string;
};

type ReasoningAttachment = {
  reasoning: BusinessReasoning | null;
  status: string;
};

type ReasoningReport = NormalizedInvestigation & {
  geminiAttachment?: ReasoningAttachment;
};

const pages: {
  name: PageName;
  icon: typeof LayoutDashboard;
  group: string;
}[] = [
  { name: "Home", icon: LayoutDashboard, group: "WORKSPACE" },
  { name: "Investigations", icon: Search, group: "WORKSPACE" },
  { name: "Reports", icon: FileSearch2, group: "WORKSPACE" },
];

function object(value: unknown): Data {
  return value !== null &&
    typeof value === "object" &&
    !Array.isArray(value)
    ? (value as Data)
    : {};
}

function array(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function string(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function label(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function display(value: unknown): string {
  if (typeof value === "number") {
    return new Intl.NumberFormat("en", {
      maximumFractionDigits: 2,
    }).format(value);
  }

  if (typeof value === "string") {
    const n = Number(value);
    if (value.trim() !== "" && Number.isFinite(n)) {
      return new Intl.NumberFormat("en", {
        maximumFractionDigits: 2,
      }).format(n);
    }
    return value;
  }

  return "—";
}

function displaySigned(value: unknown): string {
  const formatted = display(value);
  if (
    (typeof value === "number" && value > 0) ||
    (typeof value === "string" && Number(value) > 0)
  ) {
    return `+${formatted}`;
  }
  return formatted;
}

function period(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value.map((part) => string(part)).filter(Boolean).join(" — ");
}

function shortPeriod(value: unknown): string {
  if (!Array.isArray(value)) return string(value);

  const match = /^(\d{4})-(\d{2})-\d{2}$/.exec(
    String(value[0] ?? "")
  );

  return match
    ? `${new Date(
        Date.UTC(Number(match[1]), Number(match[2]) - 1, 1)
      ).toLocaleString("en", {
        month: "short",
        timeZone: "UTC",
      })} ${match[1]}`
    : String(value[0] ?? "");
}

/* ============================================================
   GEMINI BUSINESS REASONING
   Optional, unverified interpretation of governed aggregates.
   This never replaces measured evidence.
   ============================================================ */

function extractBusinessReasoning(
  source: Data | null
): ReasoningAttachment {
  if (!source) {
    return { reasoning: null, status: "NO_RESULT" };
  }

  const queue: unknown[] = [source];
  const candidates: Data[] = [];
  const seen = new Set<object>();

  while (queue.length > 0 && candidates.length < 12) {
    const value = queue.shift();

    if (
      value === null ||
      typeof value !== "object" ||
      Array.isArray(value) ||
      seen.has(value)
    ) {
      continue;
    }

    seen.add(value);
    const item = value as Data;
    candidates.push(item);

    for (const key of [
      "payload",
      "canonical_result",
      "result",
    ]) {
      const child = item[key];
      if (
        child !== null &&
        typeof child === "object" &&
        !Array.isArray(child)
      ) {
        queue.push(child);
      }
    }
  }

  let status = "NOT_RETURNED";

  for (const item of candidates) {
    if (typeof item.business_reasoning_status === "string") {
      status = item.business_reasoning_status;
    }

    const raw = object(item.business_reasoning);

    if (raw.status !== "UNVERIFIED_ANALYSIS") continue;

    const fields = [
      "business_significance",
      "possible_explanations",
      "recommended_checks",
      "maintenance_actions",
    ] as const;

    const validLists = fields.every((field) => {
      const values = raw[field];

      return (
        Array.isArray(values) &&
        values.length <= 3 &&
        values.every(
          (value) =>
            typeof value === "string" &&
            value.trim().length > 0 &&
            value.length <= 300
        )
      );
    });

    if (
      !validLists ||
      typeof raw.caveat !== "string" ||
      !raw.caveat.trim() ||
      raw.caveat.length > 250
    ) {
      continue;
    }

    return {
      status: "GENERATED",
      reasoning: raw as BusinessReasoning,
    };
  }

  return { reasoning: null, status };
}

function GeminiBusinessInsights({
  reasoning,
}: {
  reasoning: BusinessReasoning | null;
}) {
  if (!reasoning) return null;

  const sections = [
    {
      title: "What this means",
      items: reasoning.business_significance,
    },
    {
      title: "What might explain the change",
      items: reasoning.possible_explanations,
    },
    {
      title: "What to investigate next",
      items: reasoning.recommended_checks,
    },
    {
      title: "What to maintain or monitor",
      items: reasoning.maintenance_actions,
    },
  ];

  return (
    <section
      className="report-section gemini-business-insights"
      aria-label="AI business interpretation"
    >
      <span className="eyebrow">BUSINESS INTERPRETATION</span>
      <h2 style={{ marginTop: 10, marginBottom: 8 }}>
        Understanding the results
      </h2>

      <p
        style={{
          color: "var(--muted, #79776f)",
          fontSize: 13,
          lineHeight: 1.7,
          marginBottom: 22,
        }}
      >
        An AI interpretation of approved aggregate evidence.
        Possible explanations and recommendations are not
        established business causes.
      </p>

      {sections.map(({ title, items }) =>
        items.length > 0 ? (
          <div
            key={title}
            style={{
              borderTop: "1px solid #e6e3dc",
              paddingTop: 20,
              paddingBottom: 18,
            }}
          >
            <h3
              style={{
                fontSize: 16,
                fontWeight: 600,
                marginBottom: 12,
              }}
            >
              {title}
            </h3>

            <ul
              className="plain-list"
              style={{
                paddingLeft: 18,
                display: "grid",
                gap: 10,
              }}
            >
              {items.map((item, index) => (
                <li
                  key={`${title}-${index}`}
                  style={{ lineHeight: 1.7 }}
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null
      )}

      <p
        style={{
          borderTop: "1px solid #e6e3dc",
          paddingTop: 15,
          color: "var(--muted, #79776f)",
          fontSize: 12,
          lineHeight: 1.6,
        }}
      >
        {reasoning.caveat}
      </p>
    </section>
  );
}

/* ============================================================
   REPORT UTILITIES
   ============================================================ */

function downloadReport(
  report: NormalizedInvestigation,
  mode: ReportMode,
  onError: (message: string) => void
) {
  try {
    const blob = createInvestigationPdf(report, mode);

    if (blob.type !== "application/pdf" || blob.size < 500) {
      throw new Error(
        "PDF generation returned an invalid or empty file."
      );
    }

    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = href;
    anchor.download = `opslens-${mode.toLowerCase()}-report.pdf`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();

    window.setTimeout(() => URL.revokeObjectURL(href), 1500);
  } catch (error) {
    onError(
      error instanceof Error
        ? error.message
        : "PDF export failed. Please try again."
    );
  }
}

function headline(report: NormalizedInvestigation) {
  if (report.status === "evidence_gap") {
    return "The available evidence cannot answer this question yet.";
  }
  if (report.status === "clarification") {
    return "A little more detail is needed to investigate.";
  }
  if (report.status === "failed") {
    return "The investigation could not be completed.";
  }
  if (report.status !== "measured") {
    return "This result has not been verified.";
  }
  if (report.financialPremise.divergence_confirmed === true) {
    return "Revenue rose while contribution profit fell.";
  }

  const measure = report.measures[0];

  if (measure?.before !== undefined) {
    return `${label(measure.id)} ${
      Number(measure.delta) > 0
        ? "increased"
        : Number(measure.delta) < 0
        ? "decreased"
        : "was unchanged"
    }.`;
  }

  return (
    report.findings[0] ||
    "Governed measurements are available for this question."
  );
}

function executiveSummary(report: NormalizedInvestigation) {
  if (report.findings.length) return report.findings.join(" ");

  if (report.financialPremise.divergence_confirmed === true) {
    return "Revenue increased while contribution profit declined. Higher revenue did not translate into higher contribution profit across these periods.";
  }

  if (report.status === "measured") {
    return "The report contains governed measurements for the requested scope. The observed movement is descriptive and does not establish a cause.";
  }

  return report.reason || "No measured finding is available.";
}

function changeLabel(value: unknown, unit?: string) {
  return `${display(value)}${
    unit === "percentage_points"
      ? " percentage points"
      : unit === "score_points"
      ? " score points"
      : unit
      ? ` ${unit}`
      : ""
  }`;
}

function unitLabel(unit?: string) {
  return unit === "percent"
    ? "%"
    : unit === "score_1_to_5"
    ? " / 5"
    : unit
    ? ` ${unit.replaceAll("_", " ")}`
    : "";
}

function BusinessFinding({ text }: { text: string }) {
  const separator = text.indexOf(":");

  if (separator > 0 && separator < 50) {
    return (
      <li>
        <strong>{text.slice(0, separator + 1)}</strong>
        {text.slice(separator + 1)}
      </li>
    );
  }

  const sentenceEnd = text.indexOf(".");

  if (sentenceEnd > 0 && sentenceEnd < 95) {
    return (
      <li>
        <strong>{text.slice(0, sentenceEnd + 1)}</strong>
        {text.slice(sentenceEnd + 1)}
      </li>
    );
  }

  return <li>{text}</li>;
}

/* ============================================================
   BUSINESS CHARTS
   ============================================================ */

function BusinessMetricChart({
  report,
}: {
  report: NormalizedInvestigation;
}) {
  const measures = report.measures.filter(
    (m) =>
      m.before !== undefined &&
      m.after !== undefined &&
      Number.isFinite(Number(m.before)) &&
      Number.isFinite(Number(m.after))
  );

  if (!measures.length) return null;

  return (
    <section className="report-section business-chart">
      <SectionHeading
        eyebrow="VISUAL EVIDENCE"
        title="Period comparison"
        note="Each metric uses its own scale. The bars compare only the two measured periods."
      />

      {measures.map((m) => {
        const before = Number(m.before);
        const after = Number(m.after);
        const max = Math.max(
          Math.abs(before),
          Math.abs(after),
          0.0001
        );

        const prior =
          shortPeriod(m.period) ||
          shortPeriod(report.periods.before) ||
          "Earlier period";

        const current =
          shortPeriod(report.periods.after) || "Later period";

        return (
          <div className="business-chart-row" key={m.id}>
            <div className="business-chart-title">
              <strong>{label(m.id)}</strong>
              <span>
                {m.delta !== undefined
                  ? `Change ${changeLabel(
                      m.delta,
                      m.deltaUnit || m.unit
                    )}`
                  : "Measured comparison"}
              </span>
            </div>

            {[
              { name: prior, value: before, later: false },
              { name: current, value: after, later: true },
            ].map((item) => (
              <div
                className="business-bar-line"
                key={item.name}
                title={`${item.name}: ${display(
                  item.value
                )}${unitLabel(m.unit)}`}
              >
                <span>{label(item.name)}</span>
                <i>
                  <b
                    className={item.later ? "after-bar" : ""}
                    style={{
                      width: `${Math.max(
                        1,
                        (Math.abs(item.value) / max) * 100
                      )}%`,
                    }}
                  />
                </i>
                <strong>
                  {display(item.value)}
                  {unitLabel(m.unit)}
                </strong>
              </div>
            ))}

            <details className="chart-values">
              <summary>Accessible values</summary>
              <p>
                {prior}: {display(m.before)}
                {unitLabel(m.unit)} · {current}:{" "}
                {display(m.after)}
                {unitLabel(m.unit)}
                {m.delta !== undefined
                  ? ` · Change ${changeLabel(
                      m.delta,
                      m.deltaUnit || m.unit
                    )}`
                  : ""}
              </p>
            </details>
          </div>
        );
      })}
    </section>
  );
}

function BusinessPerOrderChart({
  report,
  presentation,
}: {
  report: NormalizedInvestigation;
  presentation: ReturnType<
    typeof buildBusinessReportPresentation
  >;
}) {
  const rows = presentation.perOrderComponents;
  const evidence = presentation.perOrderCostEvidence;

  if (!rows.length) return null;

  const maxValue = Math.max(
    ...rows.flatMap((row) => [
      Math.abs(row.before),
      Math.abs(row.after),
    ]),
    0.0001
  );

  const earlier =
    shortPeriod(report.periods.before) || "Earlier period";

  const later =
    shortPeriod(report.periods.after) || "Later period";

  return (
    <section className="report-section per-order-evidence">
      <SectionHeading
        eyebrow="SUPPORTING FINANCE MEASUREMENTS"
        title="Cost per eligible order"
        note={`Returned for ${
          evidence.populationBasis
        }. ${evidence.limitations.join(" ")}`}
      />

      <p className="per-order-population">
        Earlier cohort: {display(evidence.beforeOrders)} orders ·
        Later cohort: {display(evidence.afterOrders)} orders ·
        Values in dataset-reported units per order.
      </p>

      <div className="per-order-legend">
        <span>Earlier period</span>
        <span>Later period</span>
      </div>

      <div
        className="per-order-chart"
        role="table"
        aria-label="Cost per eligible order comparison"
      >
        {rows.map((row) => (
          <div
            className="per-order-row"
            role="row"
            key={row.label}
          >
            <div className="per-order-row-heading">
              <strong>{row.label}</strong>
              <span>
                Change {displaySigned(row.change)} per order
              </span>
            </div>

            {[
              { name: earlier, value: row.before, later: false },
              { name: later, value: row.after, later: true },
            ].map((item) => (
              <div
                className="per-order-bar-line"
                key={item.name}
                title={`${item.name}: ${display(
                  item.value
                )} reported units per order`}
              >
                <span>{item.name}</span>
                <i>
                  <b
                    className={
                      item.later ? "later-period-bar" : ""
                    }
                    style={{
                      width: `${Math.max(
                        1,
                        (Math.abs(item.value) / maxValue) * 100
                      )}%`,
                    }}
                  />
                </i>
                <strong>{display(item.value)}</strong>
              </div>
            ))}

            <details className="chart-values">
              <summary>Accessible values</summary>
              <p>
                {row.label}: {earlier}{" "}
                {display(row.before)}, {later}{" "}
                {display(row.after)}, change{" "}
                {displaySigned(row.change)} reported units per
                eligible order.
              </p>
            </details>
          </div>
        ))}
      </div>
    </section>
  );
}

function MetricComparison({ changes }: { changes: Data }) {
  const rows = Object.entries(changes).map(
    ([name, value]) => [name, object(value)] as const
  );

  if (!rows.length) return null;

  return (
    <section className="report-section">
      <SectionHeading
        eyebrow="OBSERVED MOVEMENT"
        title="Operational measures"
        note="Period-aligned descriptive measurements. Each row uses its own scale; changes do not establish causes."
      />
      <div
        className="measure-table"
        role="table"
        aria-label="Operational metric comparisons"
      >
        <div className="measure-row measure-header" role="row">
          <span>Metric</span>
          <span>Before</span>
          <span>After</span>
          <span>Within-metric display</span>
          <span>Change</span>
        </div>

        {rows.map(([name, row]) => {
          const ceiling = Math.max(
            Math.abs(Number(row.before)) || 0,
            Math.abs(Number(row.after)) || 0,
            1
          );

          const width = (value: unknown) => {
            const n = Math.abs(Number(value));
            return Number.isFinite(n)
              ? Math.max(2, (n / ceiling) * 100)
              : 2;
          };

          return (
            <div className="measure-row" role="row" key={name}>
              <span className="measure-label">
                {label(name)}
                {row.unit || row.delta_unit ? (
                  <small>
                    {string(row.unit || row.delta_unit)}
                  </small>
                ) : null}
              </span>
              <span>{display(row.before)}</span>
              <span>{display(row.after)}</span>

              <span
                className="change-visual"
                aria-label={`Before ${display(
                  row.before
                )}, after ${display(row.after)}`}
              >
                <i style={{ width: `${width(row.before)}%` }} />
                <i style={{ width: `${width(row.after)}%` }} />
              </span>

              <span className="change-value">
                {display(row.delta)}
                {row.delta_unit === "percentage_points"
                  ? " pp"
                  : row.delta_unit === "score_points"
                  ? " pts"
                  : ""}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AccountingPressures({
  hypotheses,
  partial = false,
}: {
  hypotheses: unknown[];
  partial?: boolean;
}) {
  if (!hypotheses.length) return null;

  const presentation = rankAccountingRows(
    hypotheses.map(object)
  );

  const maxImpact = Math.max(
    ...presentation.map((row) => Math.abs(row.impact)),
    1
  );

  return (
    <section className="report-section">
      <SectionHeading
        eyebrow="ACCOUNTING PRESSURES"
        title="Largest recorded profit contributions"
        note={`Negative values reduced profit. Ranked by recorded impact; units are shown as returned.${
          partial
            ? " This list is partial and does not reconcile to the full net profit movement."
            : ""
        }`}
      />

      <div
        className="measure-table accounting-bridge"
        role="table"
        aria-label="Ranked accounting contribution to profit"
      >
        <div className="measure-row measure-header" role="row">
          <span>Rank</span>
          <span>Cost component</span>
          <span>Relative impact</span>
          <span>Profit impact · units as returned</span>
        </div>

        {presentation.map((row, index) => (
          <div
            className="measure-row accounting-row"
            role="row"
            key={`${row.label}-${index}`}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <span className="measure-label">{row.label}</span>
            <span
              className="accounting-impact-bar"
              title={`${row.label}: ${display(row.impact)} profit impact`}
            >
              <i
                style={{
                  width: `${
                    (Math.abs(row.impact) / maxImpact) * 100
                  }%`,
                }}
              />
            </span>
            <strong className="change-value">
              {display(row.impact)}
            </strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function BusinessAccountingPressures({
  report,
  rows,
  note,
}: {
  report: NormalizedInvestigation;
  rows: { label: string; impact: number }[];
  note: string;
}) {
  if (!rows.length) return null;

  const maxImpact = Math.max(
    ...rows.map((row) => Math.abs(row.impact)),
    1
  );

  const p = buildBusinessReportPresentation(report);

  const reconciliationNote = p.accountingReconciled
    ? "The component total reconciles to the profit movement on the validated comparable basis."
    : p.unreconciledAmount !== undefined
    ? `Comparable component totals differ from the net profit movement by ${display(
        Math.abs(p.unreconciledAmount)
      )} reported units.`
    : p.accountingComparable
    ? "Inputs are marked comparable, but the response does not certify a completed reconciliation."
    : "A full net-profit reconciliation is unverified because the response does not confirm matching periods, population and units.";

  return (
    <section className="report-section">
      <SectionHeading
        eyebrow="ACCOUNTING MOVEMENT"
        title="Largest recorded profit contributions"
        note={`${note} ${reconciliationNote}`}
      />

      <div
        className="business-accounting-table"
        role="table"
        aria-label="Largest returned accounting profit contributions"
      >
        <div className="business-accounting-row business-accounting-header" role="row">
          <span>Rank</span>
          <span>Component</span>
          <span>Relative magnitude</span>
          <span>Profit impact · reported units</span>
        </div>

        {rows.map((row, index) => (
          <div
            className="business-accounting-row"
            role="row"
            key={`${row.label}-${index}`}
          >
            <span>
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="measure-label">
              {row.label}
            </span>
            <span
              className="accounting-impact-bar"
              aria-label={`${row.label} relative recorded impact`}
            >
              <i
                style={{
                  width: `${Math.max(
                    1,
                    (Math.abs(row.impact) / maxImpact) * 100
                  )}%`,
                }}
              />
            </span>
            <strong
              className={`business-accounting-amount ${
                row.impact > 0
                  ? "is-positive"
                  : row.impact < 0
                  ? "is-negative"
                  : ""
              }`}
            >
              {displaySigned(row.impact)}
            </strong>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ============================================================
   EVIDENCE AND METHODOLOGY
   ============================================================ */

function EvidenceMethodology({
  report,
  mode,
}: {
  report: ReasoningReport;
  mode: ReportMode;
}) {
  const grouped = evidenceSummary(
    buildReportPresentation(report).accountingGroup
  );

  return (
    <details className="trace-details evidence-methodology">
      <summary>
        Evidence &amp; Methodology
        <ChevronDown size={15} />
      </summary>

      <div className="trace-list">
        <section>
          <h3>Result and evidence status</h3>
          <p>
            Validation status: {label(report.rawStatus)} ·{" "}
            {label(report.status)}
          </p>
          <p>
            Causal claim:{" "}
            {report.causalClaim === false
              ? "No causal claim"
              : report.causalClaim === true
              ? "Claim present; not verified"
              : "Not supplied"}
          </p>
        </section>

        <section>
          <h3>Optional Gemini reasoning</h3>
          <p>
            Status:{" "}
            {report.geminiAttachment?.status ?? "NOT_RETURNED"}
          </p>
          <p>
            AI interpretation does not alter measured evidence
            or establish operational causes.
          </p>
        </section>

        {Object.keys(report.periods).length > 0 && (
          <section>
            <h3>Periods and scope</h3>
            {Object.entries(report.periods).map(([k, v]) => (
              <p key={k}>
                {label(k)}:{" "}
                {period(v) || string(v)}
              </p>
            ))}
            {report.domains.length > 0 && (
              <p>
                Domains:{" "}
                {report.domains.map(label).join(", ")}
              </p>
            )}
          </section>
        )}

        {mode === "Analyst" &&
          report.measures.some(
            (m) =>
              m.source ||
              m.policy ||
              m.timeBasis ||
              Object.keys(m.population ?? {}).length ||
              m.definition
          ) && (
            <section>
              <h3>Metric definitions and provenance</h3>
              {report.measures
                .filter(
                  (m) =>
                    m.source ||
                    m.policy ||
                    m.timeBasis ||
                    Object.keys(m.population ?? {}).length ||
                    m.definition
                )
                .map((m) => (
                  <article key={m.id}>
                    <strong>{label(m.id)}</strong>
                    {m.definition && (
                      <p>Definition: {m.definition}</p>
                    )}
                    {m.source && (
                      <p>
                        Source: <code>{m.source}</code>
                      </p>
                    )}
                    {m.timeBasis && (
                      <p>
                        Time basis: {label(m.timeBasis)}
                      </p>
                    )}
                    {Object.keys(m.population ?? {}).length >
                      0 && (
                      <p>
                        Eligible population:{" "}
                        {Object.entries(m.population ?? {})
                          .map(
                            ([k, v]) =>
                              `${label(k)} ${display(v)}`
                          )
                          .join(" · ")}
                      </p>
                    )}
                    {m.policy && (
                      <p>Eligibility rule: {m.policy}</p>
                    )}
                    {m.limitations.map((x) => (
                      <p key={x}>Limitation: {x}</p>
                    ))}
                  </article>
                ))}
            </section>
          )}

        {grouped.length > 0 && (
          <section>
            <h3>Accounting evidence metadata</h3>
            {grouped.map((v) => (
              <p key={v}>{v}</p>
            ))}
          </section>
        )}

        {Object.keys(report.cohortEvidence).length > 0 && (
          <section>
            <h3>Operational cohort audit</h3>
            <p>
              Status:{" "}
              {label(
                string(report.cohortEvidence.status) ||
                  "Not supplied"
              )}
            </p>
            {string(report.cohortEvidence.limitation) && (
              <p>
                Scope:{" "}
                {string(report.cohortEvidence.limitation)}
              </p>
            )}
            {array(report.cohortEvidence.months).map(
              (v, i) => {
                const row = object(v);
                return (
                  <p key={i}>
                    {string(row.month)}:{" "}
                    {display(row.orders)} audited orders
                  </p>
                );
              }
            )}
          </section>
        )}

        {mode === "Analyst" &&
          report.limitations.length > 0 && (
            <section>
              <h3>Evidence limitations</h3>
              <ul>
                {report.limitations.map((v) => (
                  <li key={v}>{v}</li>
                ))}
              </ul>
            </section>
          )}

        {mode === "Analyst" &&
          report.toolTrace.length > 0 && (
            <section>
              <h3>Governed tool trace</h3>
              {report.toolTrace.map((trace, i) => (
                <p key={i}>
                  {label(
                    string(trace.capability) ||
                      `Step ${i + 1}`
                  )}
                  {string(trace.source) && (
                    <>
                      {" "}· <code>{string(trace.source)}</code>
                    </>
                  )}
                  {string(trace.metric_id) && (
                    <> · {string(trace.metric_id)}</>
                  )}
                </p>
              ))}
            </section>
          )}

        {report.stopReasons.length > 0 && (
          <section>
            <h3>Investigation stop reasons</h3>
            {report.stopReasons.map((entry) => (
              <p key={entry.path}>
                {entry.path}: {entry.value}
              </p>
            ))}
          </section>
        )}

        <InvestigationEvidence
          report={report}
          mode={mode}
        />
      </div>
    </details>
  );
}

/* ============================================================
   INVESTIGATION REPORT
   ============================================================ */

function reportTitle(report: NormalizedInvestigation) {
  const measured = report.measures
    .map((m) => m.id)
    .filter(Boolean);

  const domains = report.domains.map(label);

  const title = report.title
    .replaceAll("_", " ")
    .trim();

  if (
    title &&
    ![
      "investigation",
      "investigation planner",
      "three domain investigation",
    ].includes(title.toLowerCase())
  ) {
    return label(title);
  }

  if (measured.length === 1) {
    return `${label(measured[0])} Investigation`;
  }

  if (domains.length) {
    return `${domains.join(" and ")} Investigation`;
  }

  return "Business Investigation";
}

function ReportHeader({
  report,
}: {
  report: NormalizedInvestigation;
}) {
  const statusLabels: Record<
    NormalizedInvestigation["status"],
    string
  > = {
    measured: "Measured evidence",
    evidence_gap: "Evidence gap",
    clarification: "Clarification needed",
    failed: "Execution failed",
    unverified: "Unverified",
  };

  const periodText = Object.entries(report.periods)
    .map(
      ([k, v]) =>
        `${label(k)}: ${period(v) || string(v)}`
    )
    .filter((v) => !v.endsWith(": "))
    .join(" · ");

  return (
    <header className="report-header">
      <div>
        <span className="eyebrow">
          INVESTIGATION REPORT
        </span>
        <h2>{reportTitle(report)}</h2>
        <p>
          {[
            ...report.domains.map(label),
            periodText,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>

      <span
        className={`report-status ${
          report.status === "measured"
            ? "is-measured"
            : report.status === "evidence_gap"
            ? "is-gap"
            : "is-neutral"
        }`}
      >
        <i />
        {statusLabels[report.status]}
      </span>
    </header>
  );
}

function BusinessReport({
  report,
  onInvestigate,
}: {
  report: ReasoningReport;
  onInvestigate?: (question: string) => void;
}) {
  const p = buildBusinessReportPresentation(report);
  const financial = report.financialPremise;

  const geminiReasoning =
    report.geminiAttachment?.reasoning ?? null;

  const financialKpis = [
    ["Revenue change", financial.revenue_delta],
    ["Contribution profit change", financial.contribution_profit_delta],
  ] as const;

  const hasValue = (value: unknown) =>
    value !== undefined &&
    value !== null &&
    !(typeof value === "string" && !value.trim()) &&
    Number.isFinite(Number(value));

  const categoryGmv = hasValue(
    report.productContext.category_item_gmv
  );

  return (
    <>
      <ReportHeader report={report} />

      <section className="business-lead">
        <span className="eyebrow">
          {report.status === "measured"
            ? "DIRECT ANSWER"
            : "INVESTIGATION DISPOSITION"}
        </span>
        <h2>{p.answer}</h2>
        {p.premise && <p>{p.premise}</p>}
      </section>

      {geminiReasoning && (
        <GeminiBusinessInsights reasoning={geminiReasoning} />
      )}

      {report.status === "measured" && (
        <>
          {(financialKpis.some(([, value]) =>
            hasValue(value)
          ) ||
            report.measures.some(
              (m) =>
                m.before === undefined &&
                m.after === undefined &&
                hasValue(m.value)
            ) ||
            categoryGmv) && (
            <section className="report-section">
              <SectionHeading
                eyebrow="KEY KPI CHANGES"
                title="Measured results"
                note={
                  Object.keys(financial).length
                    ? "Verified for the governed finance comparison."
                    : undefined
                }
              />

              {financialKpis.some(([, value]) =>
                hasValue(value)
              ) && (
                <>
                  <div className="business-kpis">
                    {financialKpis
                      .filter(([, value]) =>
                        hasValue(value)
                      )
                      .map(([name, value]) => (
                        <div key={name}>
                          <span>{name}</span>
                          <strong>
                            {displaySigned(value)}
                          </strong>
                          <small>
                            across compared periods
                          </small>
                        </div>
                      ))}
                  </div>

                  <p className="business-metric-context">
                    Amounts are shown in the dataset's
                    reported units; no currency code was supplied.
                  </p>
                </>
              )}

              {categoryGmv && (
                <div className="business-kpi-single">
                  <div>
                    <span>
                      {label(
                        string(
                          report.productContext.category
                        )
                      )}{" "}
                      Category Item Gross Merchandise
                      Value (GMV)
                    </span>
                    <strong>
                      {display(
                        report.productContext.category_item_gmv
                      )}{" "}
                      <small>reported units</small>
                    </strong>
                  </div>
                  <p>
                    {period(
                      report.productContext.period
                    )}
                  </p>
                </div>
              )}

              {report.measures
                .filter(
                  (m) =>
                    m.before === undefined &&
                    m.after === undefined &&
                    hasValue(m.value)
                )
                .map((m) => (
                  <div
                    className="business-kpi-single"
                    key={m.id}
                  >
                    <div>
                      <span>
                        {metricLabel(m.id)}
                      </span>
                      <strong>
                        {display(m.value)}{" "}
                        <small>{m.unit}</small>
                      </strong>
                    </div>
                    <p>{period(m.period)}</p>
                  </div>
                ))}

              {report.measures.some((m) =>
                /margin/i.test(m.id)
              ) && (
                <p className="business-metric-context">
                  <strong>
                    Profit and margin are different:
                  </strong>{" "}
                  contribution profit is an amount;
                  contribution margin expresses that
                  amount relative to revenue.
                </p>
              )}
            </section>
          )}

          <BusinessMetricChart report={report} />

          {p.selectedAccounting.length > 0 && (
            <BusinessAccountingPressures
              report={report}
              rows={p.selectedAccounting}
              note={p.accountingSelectionNote}
            />
          )}

          <BusinessPerOrderChart
            report={report}
            presentation={p}
          />

          {!geminiReasoning && p.findings.length > 0 && (
            <section className="report-section">
              <SectionHeading
                eyebrow="KEY FINDINGS"
                title="What matters"
              />
              <ul className="plain-list business-finding-list">
                {p.findings.slice(0, 3).map((line) => (
                  <BusinessFinding
                    key={line}
                    text={line}
                  />
                ))}
              </ul>
            </section>
          )}

          {!geminiReasoning &&
            p.businessInterpretation.length > 0 && (
              <section className="report-section">
                <SectionHeading
                  eyebrow="BUSINESS INTERPRETATION"
                  title="What the evidence means"
                />
                <ul className="plain-list business-finding-list">
                  {p.businessInterpretation
                    .slice(0, 2)
                    .map((line) => (
                      <BusinessFinding
                        key={line}
                        text={line}
                      />
                    ))}
                </ul>
              </section>
            )}
        </>
      )}

      {(p.availableFollowUps.length > 0 ||
        p.additionalEvidence.length > 0) && (
        <section className="report-section next-section">
          <SectionHeading
            eyebrow="NEXT STEPS"
            title="What to investigate next"
          />

          {p.availableFollowUps.length > 0 && (
            <>
              <h3>Available now</h3>
              <ul className="business-next-actions">
                {p.availableFollowUps.map(
                  (question) => (
                    <li key={question}>
                      <button
                        className="text-button"
                        onClick={() =>
                          onInvestigate?.(question)
                        }
                        disabled={!onInvestigate}
                      >
                        {question}
                        <ArrowRight size={14} />
                      </button>
                    </li>
                  )
                )}
              </ul>
            </>
          )}

          {p.additionalEvidence.length > 0 && (
            <div className="evidence-needed-next">
              <h3>Requires additional evidence</h3>
              <ul className="plain-list">
                {p.additionalEvidence
                  .slice(0, 3)
                  .map((item) => (
                    <li key={item}>{item}</li>
                  ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {(p.limitations.length > 0 ||
        report.accountingHypotheses.length > 0) && (
        <section className="report-section limitation-section">
          <SectionHeading
            eyebrow="LIMITATIONS"
            title="What remains uncertain"
          />
          <p>
            {report.accountingHypotheses.length > 0
              ? p.accountingReconciled
                ? "The accounting components reconcile on their validated scope; they still do not establish an operational cause."
                : p.unreconciledAmount !== undefined
                ? `Comparable accounting components differ from the net profit movement by ${display(
                    Math.abs(p.unreconciledAmount)
                  )} reported units; this residual is not attributed to a cause.`
                : p.accountingComparable
                ? "The inputs are marked comparable, but a completed net-profit reconciliation is not certified."
                : "The response does not verify that the returned accounting components and net profit movement share matching periods, population and units."
              : report.status === "measured"
              ? "The returned comparison is descriptive and does not establish what caused the movement."
              : "The measured evidence needed to answer this question is unavailable."}{" "}
            {Array.from(
              new Set(
                p.limitations.map(
                  plainLanguageLimitation
                )
              )
            ).join(" ")}
          </p>
        </section>
      )}

      <EvidenceMethodology
        report={report}
        mode="Business"
      />
    </>
  );
}

function AnalystReport({
  report,
}: {
  report: ReasoningReport;
}) {
  const p = buildReportPresentation(report);

  const comparative = report.measures.filter(
    (m) =>
      m.before !== undefined ||
      m.after !== undefined
  );

  const standalone = report.measures.filter(
    (m) =>
      m.before === undefined &&
      m.after === undefined
  );

  return (
    <>
      <ReportHeader report={report} />

      <section className="business-lead">
        <span className="eyebrow">
          DIRECT ANSWER · VERIFIED PREMISE
        </span>
        <h2>{p.answer}</h2>
        <p>{p.premise}</p>
      </section>

      {p.metrics.length > 0 && (
        <section className="report-section">
          <SectionHeading
            eyebrow="MEASURED VALUES"
            title="Period comparison"
            note="Values and deltas are shown as returned by the validated result."
          />

          {Object.keys(
            report.financialPremise
          ).length > 0 && (
            <div className="financial-grid">
              <div>
                <span>Revenue change</span>
                <strong>
                  {display(
                    report.financialPremise.revenue_delta
                  )}
                </strong>
              </div>

              <div>
                <span>Contribution profit change</span>
                <strong>
                  {display(
                    report.financialPremise
                      .contribution_profit_delta
                  )}
                </strong>
              </div>

              {typeof report.financialPremise
                .divergence_confirmed ===
                "boolean" && (
                <div>
                  <span>Premise check</span>
                  <strong>
                    {report.financialPremise
                      .divergence_confirmed
                      ? "Confirmed"
                      : "Not confirmed"}
                  </strong>
                </div>
              )}
            </div>
          )}

          {comparative.length > 0 && (
            <MetricComparison
              changes={Object.fromEntries(
                comparative.map((m) => [
                  m.id,
                  {
                    before: m.before,
                    after: m.after,
                    delta: m.delta,
                    unit: m.unit,
                    delta_unit:
                      m.deltaUnit || m.unit,
                  },
                ])
              )}
            />
          )}

          {standalone.map((m) => (
            <div
              className="business-kpi-single"
              key={m.id}
            >
              <div>
                <span>{label(m.id)}</span>
                <strong>
                  {display(m.value)}{" "}
                  <small>{m.unit}</small>
                </strong>
              </div>
              <p>{period(m.period)}</p>
            </div>
          ))}
        </section>
      )}

      {report.accountingHypotheses.length >
        0 && (
        <AccountingPressures
          hypotheses={report.accountingHypotheses}
        />
      )}

      {p.findings.length > 0 && (
        <section className="report-section">
          <SectionHeading
            eyebrow="ANALYTICAL FINDINGS"
            title="Evidence-based findings"
          />
          <ul className="plain-list">
            {p.findings.slice(0, 4).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {p.limitations.length > 0 && (
        <section className="report-section limitation-section">
          <SectionHeading
            eyebrow="LIMITATIONS & ASSUMPTIONS"
            title="What remains unverified"
          />
          <ul className="plain-list">
            {p.limitations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {p.evidenceNeeded.length > 0 && (
        <section className="report-section">
          <SectionHeading
            eyebrow="EVIDENCE GAP"
            title="Required evidence"
          />
          <ul className="plain-list">
            {p.evidenceNeeded.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      )}

      {p.validations.length > 0 && (
        <section className="report-section next-section">
          <SectionHeading
            eyebrow="PROPOSALS · VALIDATION ONLY"
            title="Prioritized next investigations"
            note="Validation proposals, not approved actions or proven remedies."
          />
          <ol className="next-list">
            {p.validations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ol>
        </section>
      )}

      <EvidenceMethodology
        report={report}
        mode="Analyst"
      />
    </>
  );
}

function InvestigationReport({
  report,
  mode,
  onInvestigate,
}: {
  report: ReasoningReport;
  mode: ReportMode;
  onInvestigate?: (question: string) => void;
}) {
  if (report.route === "refund_concentration") {
    return (
      <>
        <RefundConcentration
          report={report}
          mode={mode}
        />
        <DocumentEvidence
          report={report}
          mode={mode}
        />
        <InvestigationTimeline
          report={report}
          mode={mode}
        />
      </>
    );
  }

  if (report.route === "seller_concentration") {
    return (
      <>
        <SellerConcentration
          report={report}
          mode={mode}
        />
        <DocumentEvidence
          report={report}
          mode={mode}
        />
        <InvestigationTimeline
          report={report}
          mode={mode}
        />
      </>
    );
  }

  if (report.route === "delivery_review_comparison") {
    return (
      <>
        <DeliveryReviewComparison
          report={report}
          mode={mode}
        />
        <DocumentEvidence
          report={report}
          mode={mode}
        />
        <InvestigationTimeline
          report={report}
          mode={mode}
        />
      </>
    );
  }

  return (
    <article
      className="report"
      aria-live="polite"
    >
      {report.status === "measured" &&
        report.graphRows.length > 0 && (
          <section className="report-section">
            <SectionHeading
              eyebrow="MEASURED VALUES"
              title="Grouped measurements"
              note="Each row retains its returned dimensions and metric value."
            />
            <div className="trace-list">
              {report.graphRows.map((row, i) => (
                <p key={i}>
                  {Object.entries(row)
                    .map(
                      ([key, value]) =>
                        `${label(key)}: ${JSON.stringify(value)}`
                    )
                    .join(" · ")}
                </p>
              ))}
            </div>
          </section>
        )}

      {mode === "Business" ? (
        <BusinessReport
          report={report}
          onInvestigate={onInvestigate}
        />
      ) : (
        <AnalystReport report={report} />
      )}

      <DocumentEvidence
        report={report}
        mode={mode}
      />
      <InvestigationTimeline
        report={report}
        mode={mode}
      />
    </article>
  );
}

/* ============================================================
   WORKSPACE COMPONENTS
   ============================================================ */

function BusinessReportsWorkspace({
  report,
  mode,
  pdfError,
  onPdfError,
  onInvestigate,
}: {
  report: ReasoningReport | null;
  mode: ReportMode;
  pdfError: string;
  onPdfError: (value: string) => void;
  onInvestigate: (question: string) => void;
}) {
  return (
    <section
      className="business-workspace"
      aria-label="Business reports"
    >
      <PageHeading
        eyebrow="BUSINESS WORKSPACE"
        title="Report"
        description="A concise view of the current investigation and its evidence-backed next steps."
      />
      {report && (
        <ReportWorkspaceBody
          report={report}
          mode={mode}
          pdfError={pdfError}
          onPdfError={onPdfError}
          onInvestigate={onInvestigate}
        />
      )}
    </section>
  );
}

function AnalystReportsWorkspace({
  report,
  mode,
  pdfError,
  onPdfError,
}: {
  report: ReasoningReport | null;
  mode: ReportMode;
  pdfError: string;
  onPdfError: (value: string) => void;
}) {
  return (
    <section
      className="analyst-workspace"
      aria-label="Analyst reports"
    >
      <PageHeading
        eyebrow="ANALYST WORKSPACE"
        title="Investigation report"
        description="Precise measurements, analytical context and expandable evidence."
      />
      {report && (
        <ReportWorkspaceBody
          report={report}
          mode={mode}
          pdfError={pdfError}
          onPdfError={onPdfError}
        />
      )}
    </section>
  );
}

function ReportWorkspaceBody({
  report,
  mode,
  pdfError,
  onPdfError,
  onInvestigate,
}: {
  report: ReasoningReport;
  mode: ReportMode;
  pdfError: string;
  onPdfError: (value: string) => void;
  onInvestigate?: (question: string) => void;
}) {
  return (
    <>
      <p className="report-session-note">
        Recent investigation turns are retained in this server
        session until expiration or reset. Export evidence
        you need to keep.
      </p>

      <button
        className="primary-button report-download"
        onClick={() =>
          downloadReport(report, mode, onPdfError)
        }
      >
        <Download size={15} />
        Download {mode} PDF
      </button>

      {pdfError && (
        <p className="pdf-error" role="alert">
          {pdfError}
        </p>
      )}

      <InvestigationReport
        report={report}
        mode={mode}
        onInvestigate={onInvestigate}
      />
    </>
  );
}

type InvestigationProps = {
  question: string;
  setQuestion: (value: string) => void;
  suggestionsOpen: boolean;
  setSuggestionsOpen: (value: boolean) => void;
  run: () => void;
  loading: boolean;
  error: string;
  result: ReasoningReport | null;
  mode: ReportMode;
  onPdfError: (value: string) => void;
  onReport: () => void;
  onInvestigate: (question: string) => void;
};

function BusinessInvestigationWorkspace(
  props: InvestigationProps
) {
  return (
    <section
      className="business-workspace"
      aria-label="Business investigation workspace"
    >
      <PageHeading
        eyebrow="BUSINESS WORKSPACE"
        title="Investigations"
        description="Ask a business question, then review a concise, evidence-backed answer."
      />
      <InvestigationComposer {...props} />
      <InvestigationResult {...props} />
    </section>
  );
}

function AnalystInvestigationWorkspace(
  props: InvestigationProps
) {
  return (
    <section
      className="analyst-workspace"
      aria-label="Analyst investigation workspace"
    >
      <PageHeading
        eyebrow="ANALYST WORKSPACE"
        title="Investigations"
        description="Frame a question and inspect exact measurements, scope and supporting evidence."
      />
      <InvestigationComposer {...props} />
      <InvestigationResult {...props} />
    </section>
  );
}

function InvestigationComposer({
  question,
  setQuestion,
  suggestionsOpen,
  setSuggestionsOpen,
  run,
  loading,
  mode,
}: InvestigationProps) {
  return (
    <>
      <section
        className="composer"
        aria-label="Investigation question"
      >
        <label htmlFor="investigation-question">
          Investigation question
        </label>

        <textarea
          id="investigation-question"
          value={question}
          maxLength={500}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          onKeyDown={(event) => {
            if (
              (event.metaKey || event.ctrlKey) &&
              event.key === "Enter"
            ) {
              run();
            }
          }}
          placeholder="Ask about a metric, period, or comparison…"
        />

        <div className="composer-foot">
          <span>
            Be specific about metric and period ·{" "}
            {question.length}/500
          </span>

          <button
            className="primary-button"
            disabled={!question.trim() || loading}
            onClick={run}
          >
            {loading ? (
              <>
                <LoaderCircle
                  className="spinner"
                  size={15}
                />
                Investigating
              </>
            ) : (
              <>
                Run investigation
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </div>
      </section>

      <details
        className="question-suggestions"
        open={suggestionsOpen}
        onToggle={(event) =>
          setSuggestionsOpen(
            event.currentTarget.open
          )
        }
      >
        <summary>
          Suggested questions for {mode} view
        </summary>

        <div className="suggestion-title">
          <h2>Start with a supported question</h2>
          <p>
            Select a prompt to fill the composer.
            Submit it when ready.
          </p>
        </div>

        <div className="suggestion-list">
          {questionSuggestions[mode].map((item) => (
            <button
              type="button"
              key={item.title}
              onClick={() =>
                selectSuggestedQuestion(
                  item.question,
                  setQuestion
                )
              }
            >
              <span>
                <strong>{item.title}</strong>
                <small>{item.question}</small>
              </span>
              <ArrowRight size={15} />
            </button>
          ))}
        </div>
      </details>
    </>
  );
}

function InvestigationResult({
  result,
  error,
  loading,
  mode,
  onPdfError,
  onReport,
  onInvestigate,
}: InvestigationProps) {
  return (
    <>
      {error && (
        <div
          className="error-state"
          role="alert"
        >
          <CircleHelp size={17} />
          <div>
            <strong>Investigation unavailable</strong>
            <p>{error}</p>
            <small>
              Check the local API and PostgreSQL/MCP
              service, then try again.
            </small>
          </div>
        </div>
      )}

      {loading && (
        <div
          className="loading-state"
          role="status"
        >
          <LoaderCircle
            className="spinner"
            size={18}
          />
          <span>
            Validating the request and gathering
            approved evidence…
          </span>
        </div>
      )}

      {!loading && !error && !result && (
        <div className="empty-report">
          <FileSearch2 size={19} />
          <p>
            Your structured report will appear
            here after a question is run.
          </p>
        </div>
      )}

      {result && !loading && (
        <>
          <div className="report-actions">
            <button
              className="secondary-button"
              onClick={() =>
                downloadReport(
                  result,
                  mode,
                  onPdfError
                )
              }
            >
              <Download size={14} />
              Download {mode} PDF
            </button>

            <button
              className="text-button"
              onClick={onReport}
            >
              Open report
            </button>
          </div>

          <InvestigationReport
            report={result}
            mode={mode}
            onInvestigate={onInvestigate}
          />
        </>
      )}
    </>
  );
}

/* ============================================================
   MAIN APPLICATION
   ============================================================ */

export default function Home() {
  const [sessionClient] = useState(
    () => new InvestigationSessionClient(requestJson)
  );

  const [sessionReady, setSessionReady] = useState(false);
  const [page, setPage] = useState<PageName>("Home");
  const [question, setQuestion] = useState("");
  const [suggestionsOpen, setSuggestionsOpen] = useState(true);
  const [result, setResult] = useState<Data | null>(null);
  const [reportMode, setReportMode] =
    useState<ReportMode>("Business");

  const normalizedResult: ReasoningReport | null = result
    ? {
        ...normalizeInvestigation(result),
        geminiAttachment: extractBusinessReasoning(result),
      }
    : null;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pdfError, setPdfError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    sessionClient
      .restore(window.sessionStorage)
      .then((record) => {
        if (mounted && record) setResult(record);
      })
      .catch((cause) => {
        if (mounted) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Session could not be restored."
          );
        }
      })
      .finally(() => {
        if (mounted) setSessionReady(true);
      });

    return () => {
      mounted = false;
    };
  }, [sessionClient]);

  async function newInvestigation() {
    if (loading || !sessionReady) return;

    setLoading(true);

    try {
      await sessionClient.reset();
      setResult(null);
      setQuestion("");
      setError("");
      setPdfError("");
      setSuggestionsOpen(true);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Session reset failed."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (page === "Investigations") {
      document
        .getElementById("investigation-question")
        ?.focus();
    }
  }, [page]);

  async function runInvestigation(
    value = question
  ) {
    if (
      !value.trim() ||
      loading ||
      !sessionReady
    ) {
      return;
    }

    setPage("Investigations");
    setQuestion(value);
    setSuggestionsOpen(false);
    setLoading(true);
    setError("");

    try {
      const record = await sessionClient.turn(value);
      setResult(record);
    } catch (cause) {
      if (
        cause instanceof ApiRequestError &&
        cause.canonicalResult
      ) {
        setResult(cause.canonicalResult);
      }

      setError(
        cause instanceof Error
          ? cause.message
          : "Investigation request could not be completed."
      );
    } finally {
      setLoading(false);
    }
  }

  const title: Record<PageName, string> = {
    Home: "Home",
    Investigations: "Investigations",
    Reports: "Reports",
  };

  return (
    <div
      className={`app-shell ${
        page === "Home" &&
        reportMode === "Business"
          ? "business-home"
          : ""
      }`}
    >
      {menuOpen && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        className={`sidebar ${
          menuOpen ? "sidebar-open" : ""
        }`}
      >
        <a
          className="brand"
          href="#overview"
          onClick={(event) => {
            event.preventDefault();
            setPage("Home");
            setMenuOpen(false);
          }}
        >
          <span className="brand-symbol">O</span>
          <span>OpsLens</span>
        </a>

        <div className="sidebar-label">
          WORKSPACE
        </div>

        <nav aria-label="Main navigation" className="navigation">
          {pages
            .filter(
              ({ name }) =>
                name !== "Reports" || Boolean(result)
            )
            .map(({ name, icon: Icon, group }, index, visiblePages) => {
              const previousGroup =
                visiblePages[index - 1]?.group;

              return (
                <div key={name}>
                  {group !== previousGroup &&
                    group !== "WORKSPACE" && (
                      <div className="sidebar-label nav-group-label">
                        {group}
                      </div>
                    )}

                  <button
                    className={`nav-item ${
                      page === name
                        ? "nav-active"
                        : ""
                    }`}
                    aria-current={
                      page === name
                        ? "page"
                        : undefined
                    }
                    onClick={() => {
                      setPage(name);
                      setMenuOpen(false);
                    }}
                  >
                    <Icon
                      size={17}
                      strokeWidth={1.7}
                    />
                    <span>{name}</span>
                  </button>
                </div>
              );
            })}
        </nav>

        <div className="sidebar-bottom">
          <ShieldCheck size={15} />
          <span>
            Governed, read-only analysis
          </span>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button
            className="menu-button"
            aria-label="Open navigation"
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={19} />
          </button>

          <div className="crumb">
            OpsLens <span>/</span>{" "}
            <b>{title[page]}</b>
          </div>

          <div className="topbar-actions">
            <button
              className="text-button"
              disabled={
                loading || !sessionReady
              }
              onClick={newInvestigation}
            >
              New investigation
            </button>

            <div
              className="view-switch"
              role="group"
              aria-label="Workspace"
            >
              <span>Workspace</span>
              {(
                ["Business", "Analyst"] as const
              ).map((mode) => (
                <button
                  key={mode}
                  aria-pressed={
                    reportMode === mode
                  }
                  className={
                    reportMode === mode
                      ? "view-active"
                      : ""
                  }
                  onClick={() =>
                    setReportMode(mode)
                  }
                >
                  {mode}
                </button>
              ))}
            </div>

            <span className="local-indicator">
              <i />
              Local environment
            </span>
          </div>
        </header>

        <div className="content-wrap">
          {page === "Home" &&
            reportMode === "Business" && (
              <BusinessLanding
                onInvestigate={(value) => {
                  setQuestion(value);
                  setSuggestionsOpen(false);
                  setPage("Investigations");
                }}
                history={
                  sessionClient.session?.history ??
                  []
                }
                sessionReady={sessionReady}
                sessionError={error}
                onOpen={(record) => {
                  setResult(record);
                  setPdfError("");
                  setPage("Reports");
                }}
              />
            )}

          {page === "Home" &&
            reportMode === "Analyst" && (
              <section
                className={`${reportMode.toLowerCase()}-workspace`}
                aria-label={`${reportMode} workspace home`}
              >
                <PageHeading
                  eyebrow="ANALYST WORKSPACE"
                  title="Performance overview"
                  description="Governed KPI comparisons with definitions and source context."
                />

                <BusinessDashboard
                  mode={reportMode}
                  onInvestigate={(value) => {
                    setQuestion(value);
                    setPage("Investigations");
                  }}
                />

                {normalizedResult && (
                  <section className="home-current-report">
                    <span className="eyebrow">
                      CURRENT INVESTIGATION
                    </span>
                    <h2>
                      {headline(normalizedResult)}
                    </h2>
                    <p>
                      {executiveSummary(
                        normalizedResult
                      )}
                    </p>
                    <button
                      className="secondary-button"
                      onClick={() =>
                        setPage("Reports")
                      }
                    >
                      Open detailed report
                      <ArrowRight size={14} />
                    </button>
                  </section>
                )}
              </section>
            )}

          {page === "Investigations" &&
            (reportMode === "Business" ? (
              <BusinessInvestigationWorkspace
                question={question}
                setQuestion={setQuestion}
                suggestionsOpen={suggestionsOpen}
                setSuggestionsOpen={
                  setSuggestionsOpen
                }
                run={() =>
                  runInvestigation()
                }
                loading={loading}
                error={error}
                result={normalizedResult}
                mode={reportMode}
                onPdfError={setPdfError}
                onReport={() =>
                  setPage("Reports")
                }
                onInvestigate={(value) => {
                  setQuestion(value);
                  setSuggestionsOpen(false);
                }}
              />
            ) : (
              <AnalystInvestigationWorkspace
                question={question}
                setQuestion={setQuestion}
                suggestionsOpen={suggestionsOpen}
                setSuggestionsOpen={
                  setSuggestionsOpen
                }
                run={() =>
                  runInvestigation()
                }
                loading={loading}
                error={error}
                result={normalizedResult}
                mode={reportMode}
                onPdfError={setPdfError}
                onReport={() =>
                  setPage("Reports")
                }
                onInvestigate={(value) => {
                  setQuestion(value);
                  setSuggestionsOpen(false);
                }}
              />
            ))}

          {page === "Reports" &&
            (reportMode === "Business" ? (
              <BusinessReportsWorkspace
                report={normalizedResult}
                mode={reportMode}
                pdfError={pdfError}
                onPdfError={setPdfError}
                onInvestigate={(value) => {
                  setQuestion(value);
                  setSuggestionsOpen(false);
                  setPage("Investigations");
                }}
              />
            ) : (
              <AnalystReportsWorkspace
                report={normalizedResult}
                mode={reportMode}
                pdfError={pdfError}
                onPdfError={setPdfError}
              />
            ))}

          <footer className="page-footer">
            <span>OpsLens</span>
            <span>
              Descriptive evidence · no automated writes
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
