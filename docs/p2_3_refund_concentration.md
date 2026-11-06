# P2.3 order-linked returns and refund concentration

Supported questions include "Where are refunds concentrated among sellers in July
2018?", "How many returns in July 2018?", "Which sellers?" after a refund result,
and contextual purchase-month follow-ups. Existing Gemini period interpretation
is used when enabled; execution remains deterministic and governed. Missing years
clarify. SKU/category, causal-responsibility, reason, delivery-filtered and threshold
requests are not silently converted to the registered cohort. A month follow-up
measures the new cohort; it does not claim a two-period change or aligned observation
window. Other questions retain their existing routes.

## Cohort and calculations

The denominator is distinct `commerce.orders` purchased in the requested half-open
month. `cx.returns` contains synthetic order-linked events with `return_id`,
`order_id`, `refund_amount`, `return_date`, `return_reason` and `source_type`.
There is no SKU identifier on a return event. The analysis uses recorded linked
events across the whole dataset snapshot, including dates after purchase-month
end; it is not a refund-date report or an as-of-period-close return rate.

- Aggregate events per order before joining orders. Reject invalid/duplicated
  order IDs, invalid refund amounts, missing event IDs, or selected event IDs that
  occur more than once anywhere in the return source. Distinct multiple events
  per order are retained; their amounts are summed, not counted as extra orders.
- Return rate = orders with at least one recorded return / purchased orders.
  Positive-refund order rate uses orders whose summed refund amount is positive.
  Amounts retain source units; no currency code is invented.
- Aggregate items per order before attribution. One known distinct seller defines
  a single-seller cohort. Multiple sellers and missing item/seller mappings form
  separate buckets. Multi-item orders with one seller count once. Invalid or
  duplicated order-item identifiers reject the detailed analysis.
- Rank exclusive seller cohorts by refund amount, then returned-order count and
  seller ID. Refund share uses **all** linked cohort refunds, including shared and
  unknown buckets, not just the seller-ranked portion.
- Reconcile every bucket to the initial order/event/refund totals; reconcile seller
  rows and multi-item counts to the exclusive-seller bucket. Finite Decimal
  arithmetic preserves original amounts. Detailed results are bounded to 5,000
  sellers; overflow fails safely and retains the initial evidence.
- Source-wide unlinked events are reported separately, never inserted into the
  cohort denominator. Different purchase cohorts can have different observation
  windows. No returns, causal responsibility, SKU effects or finance accounting
  alignment are inferred from missing links or association.

## Adaptive execution and preservation

The initial governed query establishes order-linked return/refund totals. The
existing conditional follow-up coordinator selects seller concentration only when
the user requests it and validated returned orders exist. A metric-only request
or zero-return evidence stops without the detail query. Budgets, deadlines and
duplicate-action prevention remain unchanged. Detail failure or reconciliation
failure retains the original measurement and records the stop reason.

Both queries use the existing read-only MCP SQL tool and approved `commerce`/`cx`
relations. No migration, dataset mutation, arbitrary model SQL, privilege, new
framework or product/category expansion is introduced.

The canonical record includes source references, periods, populations, buckets,
full seller rows, limitations and validator archive entries. P0.3 context and P2.2
trace/replay integration are unchanged. Supporting-analysis summaries reference
`/payload/refund_analysis` and its evidence ID rather than duplicating the full
seller proof. Full source-sized evidence was verified through HTTP, session storage
and replay within the existing bounds. Business View adds relevant KPIs, a top-10
refund chart and attribution coverage; Analyst View exposes exact calculations,
events, item counts and full cohorts. PDF exports retain all evidence; the Business
summary lists the top 10 with the complete canonical evidence attached.

## Changed files

- `agent/refund_concentration.py`, `agent/refund_routing.py`: compiler, validators,
  measurement, attribution and contextual routing.
- `agent/evidence_followup.py`, `agent/session_context.py`,
  `scripts/phase5_1_playground.py`: registered adaptive branch and session/runtime
  integration.
- `frontend/components/refund-concentration.tsx`, `frontend/app/page.tsx`,
  `frontend/lib/report-pdf.ts`: existing-style report and PDF integration.
- `scripts/p2_3_validate.py`, `scripts/p2_3_live.py`, frontend comparison and
  normalization tests, `frontend/tests/fixtures/p2_3_refunds.json`: focused tests,
  real HTTP capture with mocked MCP, and bounded live checks.

## Validation scope

The source CSV oracle independently groups repository order, item and return rows,
then reconciles them through the validators. It is not evidence that PostgreSQL
executed the generated SQL. The SQL compiler passes the existing read-only guard;
live query correctness still needs verification once PostgreSQL is reachable.
Separate summary and detail queries reconcile totals but do not guarantee a common
database transaction snapshot.
