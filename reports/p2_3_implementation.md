# P2.3 implementation checkpoint

Implemented order-linked return/refund measurement and evidence-conditioned
exclusive-seller concentration, with shared/unknown attribution kept separate.
Existing governed SQL permissions, canonical evidence, sessions, replay and primary
UI styling are preserved. No product/category expansion was attempted.

Changed-file details and contract: `docs/p2_3_refund_concentration.md`.

## Verification

| Suite | Passed | Failed |
|---|---:|---:|
| P2.3 analytical/HTTP/replay/source CSV | 11 | 0 |
| P1.3 seller regression | 10 | 0 |
| P1.2 adaptive regression | 10 | 0 |
| P2.2 observability/replay | 6 | 0 |
| P0.3 sessions | 23 | 0 |
| P2.1 documents | 10 | 0 |
| Frontend/PDF | 74 | 0 |

TypeScript and production build passed. Logs are in `reports/p2_3_*.log`.
The full historical suite was not repeated.

Focused coverage includes exact Decimal reconciliation; changed seller rankings;
multiple events and multi-item orders; missing/ambiguous seller mappings; invalid
order/event/item identifiers; cross-source duplicate event IDs; malformed amounts;
period mismatch; governed SQL validation; intent/evidence branch selection; no
duplicate action; budget/timeout partial retention; HTTP contextual follow-ups;
session state; replay equality; and both workspace/PDF canonical preservation.
The full 1,247-seller source-sized record also passed HTTP, session commit and exact
replay within the existing storage limits. A redundant supporting-proof copy was
replaced with a canonical evidence reference; no seller rows were truncated.

The source-row oracle (`p2_3_csv_check.json`) independently aggregated July 2018:
6,292 purchases, 203 returned/refunded orders, 203 events, and 19,179.85 refund
amount. Single-seller: 6,176 orders / 18,521.47 refund amount. Multi-seller: 97 orders
/ 658.38 refund amount. Unknown: 19 orders / zero refunds. The 1,247 exclusive
seller cohorts reconcile exactly. These are existing repository CSV findings,
not live database results and not evidence of seller responsibility.

Example offline HTTP trace: initial summary -> four returned orders among ten
purchases -> governed seller breakdown -> validated reconciliation -> saved
canonical replay with no new analytical calls. With no returned orders or no
concentration intent, the detail action is absent. A detail timeout retains the
initial evidence and records `DEADLINE_REACHED`.

## Live result and remaining limits

Both bounded MCP attempts (July 2018 and July 2019) failed while establishing a
PostgreSQL connection at localhost:5432. `p2_3_live.json` retains actual tool calls,
errors and latency. No live measurements, Gemini journey or visual browser check
are claimed. No database contents or permissions were modified, and no retry loop
was added. The final duplicate-ID guard refinement is offline-verified only.

The capability is descriptive, purchase-cohort-based and snapshot-dependent.
Synthetic returns have no SKU attribution. Shared orders are not allocated to
sellers; refund-date cash flow, reason-level breakdown, two-period differences,
filtered cohorts and causal conclusions are outside this capability. Live SQL
execution remains the outstanding environment verification.
