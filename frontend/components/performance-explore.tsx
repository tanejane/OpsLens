
"use client";

import { useEffect, useState } from "react";
import { ArrowRight, RefreshCw } from "lucide-react";
import type {
  DashboardData,
  DashboardMetric,
} from "./BusinessDashboard";
import { requestJson } from "../lib/api-client";
import { validDashboard } from "../lib/business-overview";
import {
  dashboardInvestigationQuestion,
  dashboardPeriodLabel,
} from "../lib/dashboard";

type Props = {
  onInvestigate: (question: string) => void;
};

const METRICS = [
  { id: "revenue", name: "Revenue" },
  { id: "contribution_profit", name: "Contribution profit" },
  { id: "contribution_margin_pct", name: "Contribution margin" },
  { id: "orders", name: "Placed orders" },
  { id: "late_delivery_rate", name: "Late delivery rate" },
  { id: "average_review_score", name: "Customer review score" },
] as const;

function numeric(value: unknown): number | null {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    typeof value === "boolean"
  ) {
    return null;
  }

  const result = Number(value);
  return Number.isFinite(result) ? result : null;
}

function format(value: unknown): string {
  const number = numeric(value);
  if (number === null) return "—";

  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 2,
  }).format(number);
}

function suffix(metric?: DashboardMetric): string {
  if (metric?.unit === "percent") return "%";
  if (metric?.unit === "score_1_to_5") return " / 5";
  return "";
}

function deltaUnit(metric?: DashboardMetric): string {
  if (metric?.delta_unit === "percentage_points") return " pp";
  if (metric?.delta_unit === "score_points") return " pts";
  if (metric?.unit === "orders") return " orders";
  return "";
}

function population(
  value: Record<string, unknown> | undefined
): string[] {
  if (!value) return [];

  return Object.entries(value)
    .filter(([, count]) => numeric(count) !== null)
    .map(([key, count]) => {
      const name = key.replaceAll("_", " ");
      return `${name}: ${format(count)}`;
    });
}

function ReadingBar({
  name,
  value,
  max,
  current,
}: {
  name: string;
  value: number;
  max: number;
  current: boolean;
}) {
  const width =
    max > 0 ? Math.min(100, (Math.abs(value) / max) * 100) : 0;

  return (
    <div className="explore-bar-row">
      <span>{name}</span>
      <span className="explore-bar-track">
        <span
          className={current ? "explore-bar-current" : ""}
          style={{ width: `${width}%` }}
        />
      </span>
      <strong>{format(value)}</strong>
    </div>
  );
}

export function PerformanceExplore({
  onInvestigate,
}: Props) {
  const [month, setMonth] = useState("2018-06");
  const [selected, setSelected] = useState<string>("revenue");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

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
            "The reporting period could not be verified."
          );
        }

        setData(value);
      })
      .catch((cause) => {
        if (!active) return;

        setError(
          cause instanceof Error
            ? cause.message
            : "Performance data is unavailable."
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [month, attempt]);

  const metric = data?.metrics[selected];
  const metadata = METRICS.find((item) => item.id === selected);
  const measured =
    metric?.status === "MEASURED" &&
    numeric(metric.previous?.value) !== null &&
    numeric(metric.current?.value) !== null;

  const before = numeric(metric?.previous?.value);
  const after = numeric(metric?.current?.value);
  const max = Math.max(
    Math.abs(before ?? 0),
    Math.abs(after ?? 0),
    0
  );

  const previous = data
    ? dashboardPeriodLabel(data.periods.previous)
    : "Previous period";
  const current = data
    ? dashboardPeriodLabel(data.periods.current)
    : "Current period";

  const priorPopulation = population(
    metric?.eligibility?.previous ?? metric?.previous?.population
  );
  const currentPopulation = population(
    metric?.eligibility?.current ?? metric?.current?.population
  );

  function investigate() {
    if (!data || !measured) return;

    onInvestigate(
      dashboardInvestigationQuestion(
        selected,
        data.periods.previous,
        data.periods.current
      )
    );
  }

  return (
    <section
      className="business-overview explore-view"
      aria-label="Performance exploration"
    >
      <header className="overview-heading">
        <div>
          <p className="overview-kicker">EXPLORE</p>
          <h1>A closer look.</h1>
          <p className="explore-intro">
            Follow a measurement, understand its movement,
            and examine the evidence behind it.
          </p>
        </div>

        <div className="overview-period">
          <label htmlFor="explore-month">
            Reporting month
          </label>
          <input
            id="explore-month"
            type="month"
            value={month}
            onChange={(event) => {
              if (event.target.value) {
                setMonth(event.target.value);
              }
            }}
          />
        </div>
      </header>

      <div className="overview-period-line">
        <span>
          {loading
            ? "Loading reporting period…"
            : data
              ? `${current} compared with ${previous}`
              : "Reporting period unavailable"}
        </span>
        <span>Governed measurements</span>
      </div>

      {error && (
        <div className="overview-alert" role="alert">
          <div>
            <strong>Performance unavailable</strong>
            <p>{error}</p>
          </div>
          <button
            className="overview-link"
            onClick={() => setAttempt((value) => value + 1)}
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      )}

      <div className="explore-layout">
        <aside
          className="overview-panel explore-selection"
          aria-label="Choose a metric"
        >
          <h2>Measurements</h2>
          <p className="explore-subtitle">
            Select a metric to examine.
          </p>

          <div className="explore-metric-list">
            {METRICS.map((item) => {
              const reading = data?.metrics[item.id];
              const active = selected === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  className={`explore-metric-option ${
                    active ? "is-selected" : ""
                  }`}
                  aria-pressed={active}
                  onClick={() => setSelected(item.id)}
                >
                  <span>{item.name}</span>
                  <strong>
                    {!loading && reading?.status === "MEASURED"
                      ? `${format(reading.current?.value)}${suffix(reading)}`
                      : "—"}
                  </strong>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="explore-detail">
          <article
            className="overview-panel explore-feature"
            aria-live="polite"
          >
            <div className="explore-feature-header">
              <div>
                <p className="overview-kicker">
                  SELECTED MEASUREMENT
                </p>
                <h2>{metadata?.name || "Measurement"}</h2>
              </div>
              <span className="explore-status">
                {loading
                  ? "Loading"
                  : measured
                    ? "Measured"
                    : "Unavailable"}
              </span>
            </div>

            <div className="explore-main-value">
              {measured
                ? `${format(metric?.current?.value)}${suffix(metric)}`
                : "—"}
            </div>

            <p className="explore-change">
              {measured && numeric(metric?.delta) !== null
                ? `${metric?.direction === "INCREASED" ? "+" : ""}${format(metric?.delta)}${deltaUnit(metric)} compared with ${previous}`
                : metric?.reason ||
                  "No complete validated comparison is available."}
            </p>

            <div className="explore-divider" />

            <div className="explore-feature-header">
              <h2>Period comparison</h2>
              <span className="overview-muted">
                {previous} — {current}
              </span>
            </div>

            {measured && before !== null && after !== null ? (
              <div className="explore-bars">
                <ReadingBar
                  name={previous}
                  value={before}
                  max={max}
                  current={false}
                />
                <ReadingBar
                  name={current}
                  value={after}
                  max={max}
                  current
                />
                <p className="overview-chart-note">
                  Each bar uses a zero baseline. Negative
                  measurements, if any, use absolute bar length.
                  Exact values are shown alongside.
                </p>
              </div>
            ) : (
              <p className="explore-subtitle">
                Measurements are not estimated when unavailable.
              </p>
            )}

            <div className="explore-divider" />

            <div className="explore-next">
              <div>
                <h2>Investigate this movement</h2>
                <p>
                  Continue with the existing governed
                  investigation engine.
                </p>
              </div>
              <button
                className="overview-link"
                onClick={investigate}
                disabled={!measured}
              >
                Investigate <ArrowRight size={16} />
              </button>
            </div>
          </article>

          <article className="overview-panel explore-evidence">
            <h2>Understanding the measurement</h2>
            <p className="explore-subtitle">
              Definitions and scope belong beside the
              numbers—not across an entire dashboard.
            </p>

            <div className="explore-definition">
              <h3>Definition</h3>
              <p>
                {metric?.definition ||
                  "No metric definition was supplied."}
              </p>

              {metric?.formula && (
                <>
                  <h3>Formula</h3>
                  <p>{metric.formula}</p>
                </>
              )}
            </div>

            <details>
              <summary>Population and eligibility</summary>

              <h3>{previous}</h3>
              {priorPopulation.length ? (
                priorPopulation.map((item) => (
                  <p key={item}>{item}</p>
                ))
              ) : (
                <p>No eligible population breakdown supplied.</p>
              )}

              <h3>{current}</h3>
              {currentPopulation.length ? (
                currentPopulation.map((item) => (
                  <p key={item}>{item}</p>
                ))
              ) : (
                <p>No eligible population breakdown supplied.</p>
              )}

              {metric?.population_note && (
                <p>{metric.population_note}</p>
              )}
              {metric?.policy && (
                <p>Eligibility rule: {metric.policy}</p>
              )}
            </details>

            <details>
              <summary>Source and limitations</summary>
              <p>
                Source: {metric?.source || "Not supplied"}
              </p>
              {metric?.limitations?.map((item) => (
                <p key={item}>{item}</p>
              ))}
              {data?.limitations?.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </details>
          </article>
        </div>
      </div>

      <p className="overview-method">
        Comparisons are descriptive, not causal findings.
        Different metrics may use different eligible populations.
        Dataset-native currency is not converted.
      </p>
    </section>
  );
}
