# OpsLens Business-Layer Assumptions

This project deliberately separates **real observed Olist data** from **synthetic business augmentation**.

## Principles

1. Real Olist transaction values are never relabelled as synthetic facts.
2. Synthetic variables are attached to real keys and real time periods.
3. Randomness is deterministic with seed `20261025`.
4. Hidden incident ground truth is stored outside the agent-accessible data path.
5. Synthetic values are for agent-system evaluation, not claims about Olist's real profitability.

## Finance model

- Revenue = observed Olist item `price`.
- Product cost is estimated from each product's median real selling price and a category-specific gross-margin band.
- Product costs drift slowly over time.
- Payment processing cost = 2.1% of item revenue + 0.35 per order.
- Fulfilment cost is a deterministic function of real freight value and real product weight.
- Refunds are generated from a return model conditioned on real review and delivery outcomes.
- Marketing cost is allocated only to synthetically attributed campaign orders.

## Incident INC_001

Month: 2018-03-01

A controlled supplier-cost shock of **8.5%** is applied to:
health_beauty, watches_gifts, bed_bath_table

The `GrowthMax Revenue Push` campaign intentionally overlaps this period.

This creates a realistic investigation environment in which real observed revenue can coexist with synthetic margin pressure.

## Interpretation

Never describe synthetic cost, inventory, campaign or return records as facts about the real Olist company.
The correct portfolio phrasing is:

> Built on real anonymised Olist commerce transactions and augmented with reproducible synthetic finance and operations layers to create controlled ground truth for agent evaluation.
