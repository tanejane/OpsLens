
"""Metric-aware, bounded refund semantic assessment v2.

Shadow-only. Does not authorize execution, authenticate
provenance, or certify investigation completion.
"""

import calendar
import re
from datetime import date

MONTH = (
    r"January|February|March|April|May|June|July|"
    r"August|September|October|November|December"
)

PERIOD = rf"(?P<month>{MONTH}) (?P<year>20\d{{2}})"

# Metric identity and operation are declared together.
# Full-question matching prevents silent population filtering.
RULES = (
    (rf"what was the refund rate in {PERIOD}", "refund_rate", False),
    (rf"what was the {PERIOD} refund rate", "refund_rate", False),
    (rf"give me the {PERIOD} refund rate", "refund_rate", False),
    (rf"calculate {PERIOD} refund rate", "refund_rate", False),

    (rf"what was the return rate in {PERIOD}", "return_rate", False),

    (rf"how many orders were refunded in {PERIOD}",
     "refunded_order_count", False),

    (rf"how many orders had recorded returns in {PERIOD}",
     "returned_order_count", False),

    (rf"what was the refund amount in {PERIOD}",
     "refund_amount", False),

    (rf"what is the refund amount in {PERIOD}",
     "refund_amount", False),

    (rf"list the sellers with the highest refund amounts in {PERIOD}",
     "seller_refund_ranking", True),
)


def _normalize(question):
    if not isinstance(question, str):
        return ""
    return re.sub(r"\s+", " ", question.strip().rstrip("?.! "))


def _period(month, year):
    try:
        m = list(calendar.month_name).index(month.capitalize())
        y = int(year)
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1)
        return [start.isoformat(), end.isoformat()]
    except (ValueError, OverflowError):
        return None


def assess(question, action, supplied_metric):
    decision = {
        "contract": "opslens.refund-semantic-shadow.v2",
        "status": "NOT_VERIFIED",
        "requested_metric": None,
        "supplied_metric": supplied_metric,
        "requested_period": None,
        "operation": None,
        "execution_authorized": False,
        "completion_authorized": False,
        "evidence_state": "NOT_ASSESSED",
        "source_provenance_authenticated": False,
    }

    q = _normalize(question)
    matched = []

    for pattern, metric, detail in RULES:
        m = re.fullmatch(pattern, q, flags=re.I)
        if m:
            period = _period(m.group("month"), m.group("year"))
            if period is not None:
                matched.append((metric, detail, period))

    # Ambiguous or unknown language never receives a match.
    if len(matched) != 1:
        return decision

    metric, detail, period = matched[0]

    decision["requested_metric"] = metric
    decision["requested_period"] = period
    decision["operation"] = (
        "seller_refund_amount_ranking"
        if detail else "monthly_refund_measurement"
    )

    if type(supplied_metric) is not str or supplied_metric != metric:
        return decision

    if not isinstance(action, dict):
        return decision

    if set(action) != {"kind", "start", "end", "detail"}:
        return decision

    if (
        action.get("kind") != "refund_concentration"
        or type(action.get("detail")) is not bool
        or action["detail"] is not detail
        or type(action.get("start")) is not str
        or type(action.get("end")) is not str
        or [action["start"], action["end"]] != period
    ):
        return decision

    decision["status"] = "METRIC_PERIOD_ACTION_MATCH"
    return decision
