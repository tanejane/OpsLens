"""Static regression for previously unsupported FULL JOIN nullable category matching."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'sql'/'phase4c21_category_catalog_audit.sql'
s=p.read_text(encoding='utf-8-sig')
checks={
 'no unsupported full join': 'FULL JOIN ' not in '\n'.join(line for line in s.splitlines() if not line.lstrip().startswith('--')).upper(),
 'union populations': 'UNION ALL' in s.upper(),
 'null group preserved': 'GROUP BY raw_category' in s,
 'independent source totals': "'source_product_count'" in s and "'source_item_count'" in s and "'source_item_gmv'" in s,
 'catalog contract retained': 'opslens_product_categories_census_v1' in s,
}
for k,v in checks.items():
 print(('PASS' if v else 'FAIL')+': '+k)
assert all(checks.values()),'SQL source checks failed'
print(f'Checks passed: {len(checks)}/{len(checks)}')
