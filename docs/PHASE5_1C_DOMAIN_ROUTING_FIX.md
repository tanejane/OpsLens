# OpsLens 5.1C – Delivery Comparison Context Isolation

## Incident
After a successful late-delivery query, the sentence “Why did revenue increase while profit decreased in March 2018 compared with February 2018?” was captured by `DeliveryComparisonSession.is_comparison` because `STRONG_COMPARE` matched the comparison and the previous domain was delivery. Its date parser then emitted “Specify earlier month first and later month second.” This was **not** a financial comparison result.

## Patch
Replace only `agent/phase4c17_delivery_compare.py`. Its `is_comparison` now refuses to claim questions with explicit finance, review, or product subjects. A delivery comparison still routes normally when it has explicit delivery terms, and an elliptical comparison still uses the previous delivery context when no competing domain is named. No view, SQL, MCP permission, metrics, or interpreter schema changes.

## Validate
`python -m scripts.phase5_1c_validate`

Then run your existing `python -m scripts.phase4c17_validate`, `python -m scripts.phase5_1b_validate`, and `python -m scripts.phase5_1_validate` and start `python -m scripts.phase5_1_playground --gemini` in a **new process**. Ask the delivery question, then explicitly ask the revenue/profit comparison.

## Acceptance boundary
This repair only prevents incorrect *delivery* capture. The downstream finance investigation router may still request clarification or reject the claim based on its independent period and premise requirements. Do not treat routing success as financial investigation success.
