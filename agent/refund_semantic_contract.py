
"""Bounded refund semantic compatibility check.

Shadow-only. Does not authenticate context, approve SQL,
authorize execution, or certify evidence.
"""

import calendar
import re
from datetime import date

MONTH = (
    r"January|February|March|April|May|June|July|"
    r"August|September|October|November|December"
)
DATE = rf"(?P<month>{MONTH})\s+(?P<year>20\d{{2}})"

SHAPES = (
    (rf"calculate {DATE} refund rates?", False),
    (rf"show {DATE} refund counts?", False),
    (rf"show (?:the )?refund counts? for {DATE}", False),
    (rf"what was the refund rate in {DATE}", False),
    (rf"what was the {DATE} refund rate", False),
    (rf"what is the refund amount in {DATE}", False),
    (rf"which sellers had the most returns in {DATE}", True),
    (rf"show {DATE} refund concentration by seller", True),
)


def normalize(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip().rstrip("?.! "))


def expected_period(month, year):
    m = list(calendar.month_name).index(month.capitalize())
    y = int(year)
    if not 2016 <= y <= 2026:
        return None
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1)
    return [start.isoformat(), end.isoformat()]


def action_matches(action, period, detail):
    return (
        isinstance(action, dict)
        and set(action) == {"kind", "start", "end", "detail"}
        and action.get("kind") == "refund_concentration"
        and type(action.get("detail")) is bool
        and action["detail"] is detail
        and [action["start"], action["end"]] == period
    )


def prior_period(prior):
    # Shape check only; this does not authenticate prior.
    if not isinstance(prior, dict):
        return None
    payload = prior.get("payload")
    if not isinstance(payload, dict):
        return None
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        return None
    period = evidence.get("period")
    if (
        payload.get("route") != "refund_concentration"
        or payload.get("status") != "MEASURED_WITH_LIMITATIONS"
        or payload.get("executable") is not True
        or payload.get("causal_claim") is not False
        or not isinstance(period, list)
        or len(period) != 2
        or not all(isinstance(v, str) for v in period)
    ):
        return None
    return period


def verify(question, action, *, immediate=None, pending=None,
           prior=None, context_trusted=False):
    """Return a non-authoritative semantic assessment."""
    decision = {
        "contract": "opslens.refund-semantic-shadow.v1",
        "status": "NOT_VERIFIED",
        "matched_operation": None,
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
    }

    if immediate is not None or not isinstance(action, dict):
        return decision

    q = normalize(question)

    for expression, detail in SHAPES:
        match = re.fullmatch(expression, q, re.I)
        if match:
            period = expected_period(
                match.group("month"), match.group("year")
            )
            if period and action_matches(action, period, detail):
                return {
                    **decision,
                    "status": "SHAPE_AND_ACTION_MATCH",
                    "matched_operation": (
                        "seller_concentration" if detail
                        else "monthly_refund_measurement"
                    ),
                }
            return decision

    # Context is usable only when supplied by a trusted caller.
    # This flag is not proof of authentication. Do not expose
    # it as an HTTP request field or execution authorization.
    if not context_trusted:
        return decision

    if re.fullmatch(r"20\d{2}", q) and isinstance(pending, dict):
        if (
            set(pending) >= {"capability", "question", "detail"}
            and pending.get("capability") == "refund_concentration"
            and pending.get("detail") is False
        ):
            original = re.fullmatch(
                rf"what was the refund rate in (?P<month>{MONTH})",
                normalize(pending.get("question")),
                re.I,
            )
            if original:
                period = expected_period(original.group("month"), q)
                if period and action_matches(action, period, False):
                    return {
                        **decision,
                        "status": "CONTEXTUAL_ACTION_MATCH",
                        "matched_operation": "monthly_refund_measurement",
                    }

    retained = prior_period(prior)

    follow = re.fullmatch(rf"what about {DATE}", q, re.I)
    if follow and retained:
        period = expected_period(
            follow.group("month"), follow.group("year")
        )
        if period and action_matches(action, period, False):
            return {
                **decision,
                "status": "CONTEXTUAL_ACTION_MATCH",
                "matched_operation": "monthly_refund_measurement",
            }

    if (
        q.lower() == "which sellers"
        and retained
        and prior["payload"].get("refund_intent") is True
        and action_matches(action, retained, True)
    ):
        return {
            **decision,
            "status": "CONTEXTUAL_ACTION_MATCH",
            "matched_operation": "seller_concentration",
        }

    return decision
