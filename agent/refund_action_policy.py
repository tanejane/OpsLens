
"""Shadow-only policy for selected refund actions.

Never authorizes execution, SQL, evidence, or completion.
Unrecognized questions do not inherit a supported metric.
"""

from agent.refund_metric_binding import requested_metric
from agent.refund_semantic_v2 import assess as assess_semantics


def evaluate(question, action):
    base = {
        "contract": "opslens.refund-action-policy-shadow.v1",
        "decision": "NOT_VERIFIED",
        "requested_metric": None,
        "reason": "Question/action compatibility not established",
        "execution_authorized": False,
        "completion_authorized": False,
    }

    if action is None:
        return {
            **base,
            "decision": "NO_REFUND_ACTION",
            "reason": "No refund action supplied; other routes not assessed",
        }

    if not isinstance(action, dict):
        return base

    if action.get("kind") != "refund_concentration":
        return {
            **base,
            "decision": "OTHER_ACTION_NOT_ASSESSED",
            "reason": "Policy covers refund_concentration only",
        }

    if not isinstance(question, str):
        return base

    binding = requested_metric(question)

    if binding is None:
        return {
            **base,
            "reason": "Question is unsupported, ambiguous, or contextual",
        }

    metric, _detail = binding

    semantic = assess_semantics(question, action, metric)

    if semantic["status"] != "METRIC_PERIOD_ACTION_MATCH":
        return {
            **base,
            "requested_metric": metric,
            "reason": "Metric, period, or operation mismatch",
        }

    return {
        **base,
        "decision": "SEMANTIC_MATCH_SHADOW",
        "requested_metric": metric,
        "reason": "Bounded question/action match; no authorization",
    }
