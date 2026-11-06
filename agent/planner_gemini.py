
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from agent.planner_contract import PlannerDecision
from agent.planner_providers import PlannerProvider

load_dotenv()


class GeminiPlannerProvider(PlannerProvider):
    def __init__(self, model: str | None = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not set.")

        self.client = genai.Client(api_key=api_key)
        self.model = (
            model
            or os.getenv("OPSLENS_GEMINI_MODEL")
            or "gemini-3.5-flash-lite"
        )

    def plan(self, snapshot: dict[str, Any]) -> PlannerDecision:
        system_instruction = """
You are the planning component of OpsLens, a governed business investigation agent.

Propose exactly ONE next action from the current structured state.
You do NOT execute tools and you do NOT write SQL.

VALID ACTION RULES

metric_definition
- hypothesis_id must be null.
- Use when the target business metric has not yet been defined.

structured_test
- H1: outcome confirmation or supplier/COGS test.
- H2: marketing economics test, but only AFTER E-H2-SCHEMA exists.
- H3: product-mix test.
- H4: refund/CX test, but only AFTER E-H4-SCHEMA exists.

schema_discovery
- ONLY valid for H2 or H4.
- NEVER choose schema_discovery for H1 or H3.

knowledge_search
- H1: supplier-cost corroboration, after H1 structured support.
- H2: GrowthMax/campaign corroboration, after H2 structured support.
- Documents corroborate evidence; they do not prove causality alone.

stop
- hypothesis_id must be null.
- Only choose when H1-H4 are all no longer UNTESTED.

INVESTIGATION RULES
- First request contribution_profit metric definition if missing.
- Then confirm the reported outcome if E-OUTCOME is missing.
- Outcome confirmation is NOT causal evidence.
- Do not guess database columns.
- Do not invent evidence.
- Test competing hypotheses.
- Never include SQL in query_hint.
- query_hint is only a semantic description/search phrase.
- Base the decision only on the supplied state.
""".strip()

        prompt = (
            "Current OpsLens investigation state:\n"
            + json.dumps(snapshot, ensure_ascii=False, indent=2)
            + "\n\nChoose the single best VALID next action."
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=PlannerDecision,
                temperature=0.0,
            ),
        )

        if getattr(response, "parsed", None) is not None:
            parsed = response.parsed
            if isinstance(parsed, PlannerDecision):
                return parsed
            return PlannerDecision.model_validate(parsed)

        if not response.text:
            raise RuntimeError("Gemini returned no planner decision.")

        return PlannerDecision.model_validate_json(response.text)
