# Business landing — Phase 1

5 November 2026. Implemented in the existing Next.js application. Functional checks pass; **visual acceptance remains incomplete** because the browser screenshot API repeatedly returned `Unable to capture screenshot`. DOM inspection is not a substitute for visual inspection.

## Implementation

- `frontend/components/business-landing.tsx`: financial hero, revenue/profit comparisons, Operations & CX, question preparation, and recent owned-session investigations. Historical month selection uses the existing dashboard API. Native input and change events both update the month; this corrected an observed browser compatibility problem. Missing values remain unavailable, not zero.
- `frontend/components/business-primitives.tsx`: reusable bordered panels, signed metric changes, and two-period comparison bars. Each financial measure has its own zero-based magnitude scale; negatives retain their sign and an explanatory note.
- `frontend/lib/business-overview.ts`: finite-value guards, period validation, exact delta units, cautious result dispositions, and saved-replay URL construction.
- `frontend/app/business-overview.css`: scoped ivory, stone, taupe, charcoal and olive tokens; restrained borders, editorial hierarchy, focus states and responsive composition. Tablet header overflow found during inspection was corrected.
- `frontend/app/page.tsx`: routes only Business Home to the new landing page. Existing navigation, Analyst dashboard, investigation composer and report rendering are reused. Selecting a question prepares the existing composer; it does not automatically execute an investigation.
- `frontend/app/layout.tsx`: loads the scoped stylesheet.
- `frontend/components/BusinessDashboard.tsx`: exports the existing dashboard types for reuse; its Analyst rendering is preserved.
- `frontend/tests/business-overview.test.mjs`: seven additional regression tests.

No backend logic, API schema, database permissions, datasets or analytical contracts were changed. No new dependencies, external fonts, demonstration measurements or model calls were added.

## API and analytical context

- `GET /api/dashboard?month=YYYY-MM`: existing Next proxy and `requestJson` client. The page validates returned periods, aborts superseded requests, clears previous data while loading, and offers retry on failure.
- Revenue, contribution profit, contribution margin and placed orders use the existing governed readings and absolute month-over-month changes. Margin and delivery changes are percentage points; review changes are score points. Dataset-native currency is not relabelled as dollars.
- Financial comparisons show both returned periods. Current delivery/review denominator counts remain visible; methodology and scope are available in disclosure sections. Finance and placed-order populations are not presented as interchangeable.
- There is no dashboard cost-component endpoint. The cost entry prepares an existing governed investigation instead of fabricating a breakdown. Accounting contributions and observations are not described as causes.
- Recent investigations reuse `InvestigationSessionClient` history. Opening a record uses the existing report. Saved evidence links require saved persistence and session/run provenance and use the existing owned-session replay endpoint and HttpOnly credential flow.

## Executed verification

| Check | Result |
|---|---|
| `npm test` | **81 passed, 0 failed, 0 skipped**, final run 15,267.578 ms. Includes existing normalization, session, error and Next proxy cookie/origin tests plus seven new landing tests. |
| `npx tsc --noEmit` | Passed. Final production build also repeated TypeScript validation after the month-input fix. |
| `npm run lint` | Passed; final build also passed lint validation. |
| `node node_modules/next/dist/bin/next build` | Passed after final change. Four static pages generated; root 36.1 kB, first-load JS 139 kB. |
| Live local dashboard through production Next proxy | June 2018 versus May 2018 returned six measured metrics. UI showed revenue 865,124.31, contribution profit 158,039.31, margin 18.27%, 6,167 placed orders, late delivery 1.39% and review score 4.25/5, rounded from actual API readings. |
| Live unavailable period | January 2020 versus December 2019 returned all six metrics unavailable. Browser month selection updated periods and showed dashes/unavailable comparisons, without stale June values. |
| Live investigation handoff | “Look at delivery” prepared the existing composer. Explicit Run returned the governed June 2018 delivery result, with scope limits. |
| Live history/report/replay | New result appeared in Recent investigations, reopened the existing report and survived page reload. Saved JSON replay returned `SAVED_EVIDENCE_ONLY`, `external_calls: 0`, and the expected canonical result. |
| Analyst navigation | Switching from Business Home displayed the existing Analyst workspace and current-investigation access. |
| Responsive DOM geometry | No right-edge overflow at reported CSS viewport widths 1440, 780 and 480 after the tablet fix. Narrow layout ordered hero, financial movement, Operations & CX, investigation entry, then history. |

Live checks used temporary local servers (Next 3010, API 8010), configured local origin and a separate QA trace store. Gemini credentials were blank in the QA process; returned replay confirmed `MODEL_DISABLED` and no model calls. Initial mismatched-origin submission correctly returned 403; the local QA origin was corrected before rerunning successfully. These checks are local API/database integration, not live Gemini verification or production deployment.

## Remaining work and acceptance limits

1. Complete screenshot-based desktop/mobile review for optical alignment, typography, contrast and focus visibility. Screenshot capture failed in the available browser. Viewport overrides also bottomed out at a reported width of 480px; 320–430px device layouts and real touch interactions remain unverified. Keyboard Tab was exercised on the month field, but a full keyboard/screen-reader accessibility audit was not completed.
2. Future phases can refine Analyst and investigation-result presentation. They were deliberately preserved. During the live check, the existing report's “What matters” formatting split the decimal `1.39` between a bold fragment and the remaining text; the direct answer and measurement were correct. Track this for the results phase.
3. Cost-component display remains investigation-backed, pending any separately approved dashboard contract work. The underlying backend release blockers and analytical limitations in `FINAL_BACKEND_ACCEPTANCE.md` are unchanged.

Phase 1 implementation and executed functional gates pass. Do not treat this document as full visual or overall release acceptance.
