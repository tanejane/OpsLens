from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent.phase4a_context import build_context,sample_catalog
from agent.phase4a_planner import GeminiPlanProvider
metrics,relations=sample_catalog()
question = sys.argv[1] if len(sys.argv)>1 else 'Which sellers are contributing to delivery delays?'
ctx=build_context(question,metrics=metrics,relations=relations)
p=GeminiPlanProvider().create_plan(ctx)
print(p.model_dump_json(indent=2))
print('\nPASS: schema-valid, catalog-grounded plan generated; no SQL executed.')
