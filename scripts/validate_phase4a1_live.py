from __future__ import annotations
import asyncio,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from agent.phase4a1_live_context import build_live_context, CatalogProtocolError

async def main():
    question='Why did customer reviews decline in June 2018?'
    try:
        context,provenance=await build_live_context(question,max_chars=14000)
    except Exception as exc:
        print('VERDICT: REVIEW — MCP catalog unavailable or incompatible')
        print(f'{type(exc).__name__}: {exc}')
        raise SystemExit(1)
    print('Catalog provenance:',provenance)
    print('Metrics:',[m['name'] for m in context.metric_catalog])
    print('Relations:',[r['name'] for r in context.relation_catalog])
    checks=[
        ('Live catalog supplied',provenance['source']=='live_mcp'),
        ('Live metrics present',bool(context.metric_catalog)),
        ('Live relations present',bool(context.relation_catalog)),
        ('CX review metric present',any(m['name']=='effective_review_score' for m in context.metric_catalog)),
        ('Review relation present',any(r['name']=='cx.effective_reviews' for r in context.relation_catalog)),
        ('Delivery relation present',any(r['name']=='operations.delivery_effective' for r in context.relation_catalog)),
        ('No restricted catalog paths',all(not r['name'].startswith(('staging.','observability.')) for r in context.relation_catalog)),
        ('Bounded context',context.context_chars<=14000),
    ]
    for label,ok in checks: print(f'[{"PASS" if ok else "FAIL"}] {label}')
    score=sum(bool(v) for _,v in checks)
    print(f'Checks passed: {score}/{len(checks)}')
    print('VERDICT:', 'PASS' if score==len(checks) else 'REVIEW')
    if score<len(checks): raise SystemExit(1)

if __name__=='__main__': asyncio.run(main())
