
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.planner_gemini import GeminiPlannerProvider
from agent.proposal_compiler import ProposalRejected, compile_proposal

if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
    print("SKIP: GEMINI_API_KEY or GOOGLE_API_KEY is not set.")
    raise SystemExit(0)

provider = GeminiPlannerProvider()

snapshot = {
    "question": "Why did profit drop even though sales went up?",
    "parsed_question": {
        "intent": "root_cause_investigation",
        "primary_metric": "contribution_profit",
        "comparison_metric": "revenue",
        "asks_for_root_cause": True,
    },
    "hypothesis_statuses": {
        "H1": "UNTESTED",
        "H2": "UNTESTED",
        "H3": "UNTESTED",
        "H4": "UNTESTED",
    },
    "evidence_ids": [],
    "evidence_summary": [],
    "remaining_step_budget": 16,
    "remaining_tool_budget": 16,
}

decision = provider.plan(snapshot)

print("=" * 92)
print("OPSLENS GEMINI PLANNER SMOKE TEST v2")
print("=" * 92)
print("Model:", provider.model)
print(decision.model_dump_json(indent=2))

compiler_state = {
    "hypotheses": {
        "H1": {"status": "UNTESTED"},
        "H2": {"status": "UNTESTED"},
        "H3": {"status": "UNTESTED"},
        "H4": {"status": "UNTESTED"},
    },
    "evidence_ledger": [],
}

try:
    action = compile_proposal(decision, compiler_state)
except ProposalRejected as exc:
    print("\n[FAIL] Planner decision is structurally valid but not executable:")
    print(exc)
    raise SystemExit(1)

print("\nCompiled governed action:")
print(action["action_id"] if action else "STOP")
print("\nVERDICT: PASS")
