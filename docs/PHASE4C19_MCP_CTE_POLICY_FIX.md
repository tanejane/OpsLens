# Phase 4C.19B MCP query-shape fix

The live MCP rejection `Unqualified relation 'totals' is not allowed` occurred because the previous SQL used named common-table expressions (`base`, `totals`, `selected`), and the MCP source-policy layer treated the CTE reference as an unqualified database relation. This correction changes only `agent/phase4c19_product.py`, and does not relax the policy, grant access, or alter metrics.

The aggregate is now a `SELECT totals.*, selected.*` with two independent derived aggregate subqueries, each reading `semantic.order_item_product_evidence_v1` with an explicit schema qualification and the same date bounds. This may read the source twice and could be less efficient than the CTE version. The `validate_metric` evidence contract is unchanged.

From the repository root, run:

```
python -m scripts.phase4c19_validate
python -m scripts.phase4c19_policy_regression
python -m scripts.phase4c19b_validate
python -m scripts.phase4c19b_live_mcp 2018-06-01 2018-07-01 health_beauty | Set-Content .\phase4c19b_mcp.json -Encoding utf8
```

Use the existing independently generated `phase4c19b_pg.json` and execute:

```
python -m scripts.phase4c19b_compare .\phase4c19b_mcp.json .\phase4c19b_pg.json
```

If MCP still rejects this SQL, capture the precise policy error and do not bypass the policy. Offline checks cannot certify the live MCP allowlist or the independent numeric reconciliation.
