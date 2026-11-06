from __future__ import annotations
import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from agent.phase4a1_live_context import build_live_context
from agent.phase4a_planner import GeminiPlanProvider

async def main():
    question=' '.join(sys.argv[1:]) or 'Why did customer reviews decline in June 2018?'
    ctx,provenance=await build_live_context(question,max_chars=14000)
    print('Context provenance:',provenance)
    plan=GeminiPlanProvider().create_plan(ctx)
    print(plan.model_dump_json(indent=2))
    print('PASS: Gemini plan validated against LIVE MCP catalog; no SQL executed.')

if __name__=='__main__': asyncio.run(main())
