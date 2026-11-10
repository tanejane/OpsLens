
"""Experimental structured Gemini proposer. Not executable."""

import json

from google.genai import types

from agent.structured_semantic_intent import validate_intent


MAX_RESPONSE_BYTES = 16384

SYSTEM_INSTRUCTION = """
Extract the user's analytical request as one JSON object.

Use EXACTLY these top-level fields:
contract, handling, metric, period, operations, clarifications,
execution_authorized, completion_eligible, evidence_state.

contract: opslens.structured-intent.v1
execution_authorized: false
completion_eligible: false
evidence_state: NOT_ASSESSED

handling must be one of:
SUPPORTED_CANDIDATE, UNSUPPORTED_SCOPE,
UNSUPPORTED_CAUSAL, CLARIFICATION_REQUIRED,
SCOPE_REVIEW_REQUIRED.

metric: lowercase snake_case identifier for the requested measurement.
period: YYYY-MM if unambiguous; otherwise null.

operations: array of typed analytical operations.
FILTER: {"kind":"FILTER","field":"...","operator":"...","value":...}
GROUPING: {"kind":"GROUPING","field":"..."}
COMPARISON: {"kind":"COMPARISON","field":"..."}

Allowed filter operators: eq, gt, gte, lt, lte, in.

Preserve exact requested thresholds and population restrictions.
Use FILTER for restrictions on included records.
Use GROUPING only when the user requests a breakdown.
Never replace a filter with a grouping.
Do not add analytical operations not requested.

For "above RM200", use FILTER order_value_myr gt 200.
For "paid by credit card", use FILTER payment_method eq credit_card.
Both filters must appear when both are requested.

An unspecified holiday period needs clarification:
handling CLARIFICATION_REQUIRED, period null,
and a nonempty clarifications array.

For unsupported analytical requirements, use UNSUPPORTED_SCOPE.
For unsupported causal identification, use UNSUPPORTED_CAUSAL.
SUPPORTED_CANDIDATE never means the database or tools are verified.

The output is untrusted analytical interpretation.
Never include SQL, tool calls, execution instructions, or evidence claims.
Return JSON only.
"""


class StructuredGenerationError(Exception):
    """Provider, parsing or validation failure."""


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON key")
        obj[key] = value
    return obj


class StructuredGeminiProposer:
    def __init__(self, client, model):
        if client is None or not isinstance(model, str) or not model.strip():
            raise ValueError("Client and explicit model required")
        self.client = client
        self.model = model

    def propose(self, question):
        if (
            not isinstance(question, str)
            or not question.strip()
            or len(question) > 4000
        ):
            raise ValueError("Invalid question")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=question,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    temperature=0,
                    max_output_tokens=2048,
                ),
            )

            raw = getattr(response, "text", None)
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("Empty model response")

            if len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise ValueError("Oversized model response")

            candidate = json.loads(
                raw,
                object_pairs_hook=_unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    ValueError("Invalid JSON constant")
                ),
            )

            validate_intent(candidate)
            return candidate

        except Exception as exc:
            raise StructuredGenerationError(
                "Structured proposal rejected"
            ) from exc
