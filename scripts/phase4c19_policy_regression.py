"""Regression for the product MCP query shape; no network or database required."""
from agent.phase4c19_product import compile_metric
for metric in ('category_order_count','units_sold','item_gmv','average_item_price','category_gmv_share'):
    sql=compile_metric(metric,'2018-06-01','2018-07-01','health_beauty')['sql']
    assert sql.count('FROM semantic.order_item_product_evidence_v1') == 2
    assert 'WITH base AS' not in sql and 'FROM base' not in sql and 'FROM totals ' not in sql
    assert 'CROSS JOIN (' in sql
    assert "category='health_beauty'" in sql
    print('PASS: schema-qualified product query',metric)
print('Checks passed: 5/5')
