
"""Shadow-only contextual refund binding.

Inputs must be obtained from server-managed state by the caller.
This module does not authenticate them or authorize execution.
"""
import re
from agent.refund_action_policy import evaluate

MONTHS = (
    "January February March April May June July August "
    "September October November December"
).split()

MONTH_RE = "(?:" + "|".join(MONTHS) + ")"
PERIOD_RE = re.compile(
    rf"\b{MONTH_RE}\s+20\d{{2}}\b", re.I
)

def _result(reason, canonical=None, metric=None):
    return {
        "status": (
            "CONTEXT_SEMANTIC_MATCH_SHADOW"
            if canonical is not None else "NOT_VERIFIED"
        ),
        "canonical_question": canonical,
        "requested_metric": metric,
        "reason": reason,
        "execution_authorized": False,
        "completion_authorized": False,
        "session_authenticated": False,
    }

def assess(question, action, *, prior=None, pending=None):
    if not isinstance(question, str) or not isinstance(action, dict):
        return _result("Missing question or action")

    if action.get("kind") != "refund_concentration":
        return _result("Not a refund action")

    q = question.strip()

    # Case 1: completion of a pending-year clarification.
    if re.fullmatch(r"20\d{2}", q):
        if not isinstance(pending, dict):
            return _result("No pending clarification")

        if pending.get("capability") != "refund_concentration":
            return _result("Wrong pending capability")

        original = pending.get("question")
        if not isinstance(original, str):
            return _result("Missing pending question")

        # The question must terminate in an explicit month without year.
        match = re.fullmatch(
            rf"(.+\bin\s+{MONTH_RE})",
            original.strip(),
            re.I,
        )
        if not match:
            return _result("Unsupported pending question")

        canonical = match.group(1) + " " + q + "?"

        verdict = evaluate(canonical, action)
        if verdict["decision"] != "SEMANTIC_MATCH_SHADOW":
            return _result("Reconstructed question/action mismatch")

        return _result(
            "Pending question reconstructed and matched",
            canonical,
            verdict["requested_metric"],
        )

    # Case 2: month/year follow-up from a validated previous record.
    follow = re.fullmatch(
        rf"What about ({MONTH_RE}) (20\d{{2}})\?",
        q,
        re.I,
    )

    if follow is None:
        return _result("Unsupported contextual form")

    if not isinstance(prior, dict):
        return _result("No previous validated record")

    payload = prior.get("payload")
    if not isinstance(payload, dict):
        return _result("Invalid previous record")

    if (
        payload.get("route") != "refund_concentration"
        or payload.get("executable") is not True
        or payload.get("causal_claim") is not False
        or payload.get("status") not in {
            "MEASURED_WITH_LIMITATIONS",
            "MEASURED_WITH_SCOPE_LIMITS",
        }
    ):
        return _result("Previous record is not an eligible measurement")

    original = prior.get("question")
    evidence = payload.get("evidence")

    if not isinstance(original, str) or not isinstance(evidence, dict):
        return _result("Missing original question or evidence")

    old_period = evidence.get("period")

    if (
        not isinstance(old_period, (list, tuple))
        or len(old_period) != 2
        or not all(isinstance(x, str) for x in old_period)
    ):
        return _result("Previous reporting period unavailable")

    # Validate the original question against the previous period.
    from agent.refund_metric_binding import requested_metric

    original_binding = requested_metric(original)
    if original_binding is None:
        return _result("Original metric cannot be established")

    old_metric, old_detail = original_binding

    previous_action = {
        "kind": "refund_concentration",
        "start": old_period[0],
        "end": old_period[1],
        "detail": old_detail,
    }

    previous_verdict = evaluate(original, previous_action)
    if previous_verdict["decision"] != "SEMANTIC_MATCH_SHADOW":
        return _result("Original question and evidence period disagree")

    recorded_metric = evidence.get("metric_id")
    if recorded_metric is not None and recorded_metric != old_metric:
        return _result("Recorded metric disagrees with original question")

    matches = list(PERIOD_RE.finditer(original))
    if len(matches) != 1:
        return _result("Original question has ambiguous period")

    replacement = follow.group(1).capitalize() + " " + follow.group(2)

    canonical = (
        original[:matches[0].start()]
        + replacement
        + original[matches[0].end():]
    )

    verdict = evaluate(canonical, action)
    if (
        verdict["decision"] != "SEMANTIC_MATCH_SHADOW"
        or verdict["requested_metric"] != old_metric
    ):
        return _result("Follow-up metric, period or operation mismatch")

    return _result(
        "Prior validated question reconstructed and matched",
        canonical,
        old_metric,
    )
