
"""Bounded, shadow-only refund question-to-metric binding.

Positive recognition is not execution approval, provenance
authentication, evidence validation or completion approval.
"""
import re

MONTH = (
    r"January|February|March|April|May|June|"
    r"July|August|September|October|November|December"
)
PERIOD = rf"(?:{MONTH})\s+20\d{{2}}"

# Full-question patterns only. No substring acceptance.
# These entries are intentionally narrow and do not grant
# any capability or execution authority.
RULES = (
    (
        rf"what was the refund rate in {PERIOD}",
        "refund_rate",
        False,
    ),
    (
        rf"what was the {PERIOD} refund rate",
        "refund_rate",
        False,
    ),
    (
        rf"give me the {PERIOD} refund rate",
        "refund_rate",
        False,
    ),
    (
        rf"calculate {PERIOD} refund rate",
        "refund_rate",
        False,
    ),
    (
        rf"what was the return rate in {PERIOD}",
        "return_rate",
        False,
    ),
    (
        rf"how many orders were refunded in {PERIOD}",
        "refunded_order_count",
        False,
    ),
    (
        rf"how many orders had recorded returns in {PERIOD}",
        "returned_order_count",
        False,
    ),
    (
        rf"what was the refund amount in {PERIOD}",
        "refund_amount",
        False,
    ),
    (
        rf"what is the refund amount in {PERIOD}",
        "refund_amount",
        False,
    ),
    (
        rf"list the sellers with the highest refund amounts in {PERIOD}",
        "seller_refund_ranking",
        True,
    ),
)


def requested_metric(question):
    if not isinstance(question, str):
        return None

    q = re.sub(
        r"\s+", " ",
        question.strip().rstrip("?.! "),
    )

    if not q:
        return None

    matches = [
        (metric, detail)
        for pattern, metric, detail in RULES
        if re.fullmatch(pattern, q, flags=re.I)
    ]

    # Ambiguous or unrecognized => no metric binding.
    return matches[0] if len(matches) == 1 else None


def assess(question, metric, action):
    base = {
        "contract": "opslens.refund-metric-binding-shadow.v1",
        "status": "NOT_BOUND",
        "requested_metric": None,
        "supplied_metric": metric,
        "execution_authorized": False,
        "completion_authorized": False,
        "source_provenance_authenticated": False,
    }

    requested = requested_metric(question)

    if requested is None:
        return base

    wanted_metric, detail = requested

    base["requested_metric"] = wanted_metric

    if metric != wanted_metric:
        return base

    # This verifies operation shape only. Exact period matching
    # remains the responsibility of a separate semantic check.
    if not isinstance(action, dict):
        return base

    if set(action) != {"kind", "start", "end", "detail"}:
        return base

    if (
        action.get("kind") != "refund_concentration"
        or type(action.get("detail")) is not bool
        or action["detail"] is not detail
    ):
        return base

    base["status"] = "METRIC_AND_OPERATION_BOUND"
    return base
