from __future__ import annotations
import os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from agent.planner_providers import OpenAIResponsesPlannerProvider
if not os.getenv('OPENAI_API_KEY'):
    print('SKIP: OPENAI_API_KEY is not set.'); raise SystemExit(0)
p=OpenAIResponsesPlannerProvider()
s={'question':'Why did profit drop even though sales went up?','parsed_question':{'intent':'root_cause_investigation','primary_metric':'contribution_profit','comparison_metric':'revenue'},'hypothesis_statuses':{'H1':'UNTESTED','H2':'UNTESTED','H3':'UNTESTED','H4':'UNTESTED'},'evidence_ids':[],'evidence_summary':[],'remaining_step_budget':16,'remaining_tool_budget':16}
print(p.plan(s).model_dump_json(indent=2))
