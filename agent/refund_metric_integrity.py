"""Supplementary, shadow-only refund metric integrity checks.

No SQL authorization, completion approval, provenance authentication,
or replacement of the original governed validators.
"""

from decimal import Decimal, InvalidOperation
from agent.evidence_coverage import verify

SUPPORTED = frozenset({
    "refund_rate",
    "return_rate",
    "refunded_order_count",
    "returned_order_count",
    "refund_amount",
    "seller_refund_ranking",
})


def _decimal(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _result(status, metric, reason):
    return {
        "contract": "opslens.refund-metric-integrity-shadow.v1",
        "status": status,
        "metric": metric,
        "reason": reason,
        "retained_consistency_checked": True,
        "source_provenance_authenticated": False,
        "original_validator_reexecuted": False,
        "execution_authorized": False,
        "completion_authorized": False,
    }


def assess(result, period, requested_metric):
    def reject(reason):
        return _result("NOT_DEMONSTRATED", requested_metric, reason)

    if requested_metric not in SUPPORTED:
        return reject("Metric not registered in this assessment")

    if (
        not isinstance(period, (list, tuple))
        or len(period) != 2
        or not all(type(x) is str for x in period)
    ):
        return reject("Invalid period specification")

    if not isinstance(result, dict):
        return reject("Invalid investigation result")

    if verify(result, "monthly_returns", period) is None:
        return reject("Monthly retained evidence not demonstrated")

    pop = result["evidence"]["population"]
    keys = ("orders", "returned_orders", "refunded_orders", "events")

    if not all(type(pop.get(k)) is int for k in keys):
        return reject("Missing or invalid population counts")

    orders = pop["orders"]
    returned = pop["returned_orders"]
    refunded = pop["refunded_orders"]
    events = pop["events"]

    if not (
        orders > 0
        and 0 <= refunded <= returned <= orders
        and events >= returned
    ):
        return reject("Population constraints contradicted")

    amount = _decimal(pop.get("refund_amount"))
    refund_rate = _decimal(pop.get("refund_rate_pct"))
    return_rate = _decimal(pop.get("return_rate_pct"))

    if any(x is None for x in (amount, refund_rate, return_rate)):
        return reject("Metric value missing or nonfinite")

    if amount < 0 or (amount > 0) != (refunded > 0):
        return reject("Refund amount/count contradiction")

    tolerance = Decimal("0.000001")
    expected_refund = Decimal(100) * refunded / orders
    expected_return = Decimal(100) * returned / orders

    if (
        abs(refund_rate - expected_refund) > tolerance
        or abs(return_rate - expected_return) > tolerance
    ):
        return reject("Derived rate arithmetic inconsistent")

    if requested_metric != "seller_refund_ranking":
        return _result(
            "INTEGRITY_AND_RETAINED_MATCH",
            requested_metric,
            "Requested metric present with consistent arithmetic",
        )

    if verify(result, "refund_sellers", period) is None:
        return reject("Seller retained evidence not demonstrated")

    detail = result.get("refund_analysis")
    if not isinstance(detail, dict) or detail.get("population") != pop:
        return reject("Seller population mismatch")

    sellers = detail.get("sellers")
    if not isinstance(sellers, list) or not sellers:
        return reject("No ranked seller records demonstrated")

    ranked = []
    seen = set()
    seller_total = Decimal(0)

    for seller in sellers:
        if not isinstance(seller, dict):
            return reject("Malformed seller record")

        sid = seller.get("seller_id")
        value = _decimal(seller.get("refund_amount"))
        s_orders = seller.get("orders")
        s_returned = seller.get("returned_orders")

        if (
            not isinstance(sid, str)
            or not sid.strip()
            or sid in seen
            or value is None
            or value < 0
            or type(s_orders) is not int
            or type(s_returned) is not int
            or not 0 <= s_returned <= s_orders
        ):
            return reject("Invalid or duplicated seller data")

        seen.add(sid)
        seller_total += value
        ranked.append((sid, value, s_returned))

    if seller_total > amount:
        return reject("Seller amounts exceed overall refund amount")

    if ranked != sorted(
        ranked,
        key=lambda item: (-item[1], -item[2], item[0]),
    ):
        return reject("Seller ranking order inconsistent")

    return _result(
        "INTEGRITY_AND_RETAINED_MATCH",
        requested_metric,
        "Retained seller records and basic ranking checks agree",
    )
