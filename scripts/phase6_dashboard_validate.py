"""Contract and rule checks for the monthly governed dashboard adapter.

Synthetic values below are disposable rule-test inputs only, never saved as
fixtures or shown by the application.
"""
from dashboard_api import assemble_dashboard, month_period


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print("PASS:", name)


def reading(value, unit="dataset_currency"):
    return {"value": value, "unit": unit, "source": "test-only", "limitations": []}


def main():
    previous, current = month_period("2018-06")
    check("selected month uses exact half-open calendar bounds", current == ["2018-06-01", "2018-07-01"])
    check("comparison is immediately preceding calendar month", previous == ["2018-05-01", "2018-06-01"])
    p, c = month_period("2018-01")
    check("January comparison rolls back across year boundary", p == ["2017-12-01", "2018-01-01"] and c == ["2018-01-01", "2018-02-01"])
    for invalid in ("2018-13", "2018-00", "2018-6", "; DROP TABLE x"):
        try:
            month_period(invalid)
            raise AssertionError("unsafe/invalid month accepted")
        except ValueError:
            pass
    check("malformed periods and SQL-like input are rejected", True)

    # Sentinel numbers only exercise comparison logic and are not business observations.
    measurements = {
        "revenue": {"previous": reading("10"), "current": reading("12")},
        "contribution_profit": {"previous": reading("7"), "current": reading("6")},
        "contribution_margin_pct": {"previous": reading("70", "percent"), "current": reading("50", "percent")},
        "orders": {"previous": reading("2", "orders"), "current": reading("3", "orders")},
        "late_delivery_rate": {"previous": reading("1", "percent"), "current": reading("2", "percent")},
        "average_review_score": {"previous": reading("4", "score_1_to_5"), "current": reading("3", "score_1_to_5")},
    }
    payload = assemble_dashboard("2018-06", current, previous, measurements)
    check("revenue/profit rule flags direction only, without causal or incident status", len(payload["noteworthy_movements"]) == 2 and all(item["causal_claim"] is False and item["validated_incident"] is False for item in payload["noteworthy_movements"]))
    check("margin delta is reported in percentage points", payload["metrics"]["contribution_margin_pct"]["delta_unit"] == "percentage_points")
    missing = assemble_dashboard("2018-06", current, previous, {**measurements, "orders": {"reason": "no approved result"}})
    check("missing KPI stays unavailable without a zero or interpolated value", missing["metrics"]["orders"]["status"] == "UNAVAILABLE" and "current" not in missing["metrics"]["orders"])
    flat = assemble_dashboard("2018-06", current, previous, {key: {"previous": reading("1", "percent"), "current": reading("1", "percent")} for key in measurements})
    check("no rule is raised when direction conditions do not hold", flat["noteworthy_movements"] == [])


if __name__ == "__main__":
    main()
