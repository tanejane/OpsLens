"""Evidence-conditioned, governed marketing composition analysis.

Descriptive only. No causal inference, unrestricted SQL, or new permissions.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from agent.investigation_result import retain_validated


class MarketingRejected(ValueError):
    pass


def money(value):
    if value is None or isinstance(value, bool):
        raise MarketingRejected("Missing monetary value")
    try:
        x = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise MarketingRejected("Invalid monetary value") from exc
    if not x.is_finite() or x < 0:
        raise MarketingRejected("Invalid monetary amount")
    return x


def periods(result):
    try:
        p = result["driver_discovery"]["period_evidence"]
        before = p["before"]["period"]
        after = p["after"]["period"]
        tokens = [*before, *after]
        if len(tokens) != 4 or any(
            not isinstance(x, str) or len(x) != 10 for x in tokens
        ):
            raise ValueError("Invalid date tokens")
        b0, b1, a0, a1 = [date.fromisoformat(x) for x in tokens]
        if not (
            b0 < b1 == a0 < a1
            and 1 <= (b1 - b0).days <= 62
            and 1 <= (a1 - a0).days <= 62
        ):
            raise ValueError("Invalid comparison windows")
        return tokens
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketingRejected("Unsupported finance periods") from exc


def accounting(result):
    components = result["driver_discovery"]["components"]
    matches = [
        x for x in components
        if isinstance(x, dict)
        and x.get("component") == "marketing_cost_effective"
    ]
    if len(matches) != 1:
        raise MarketingRejected("Marketing component not unique")
    row = matches[0]
    before, after = money(row["before"]), money(row["after"])
    delta = Decimal(str(row["delta"]))
    if not delta.is_finite() or abs(after - before - delta) > Decimal("0.02"):
        raise MarketingRejected("Accounting movement inconsistent")
    return before, after


def eligible(result):
    if not isinstance(result, dict):
        return False
    if result.get("route") != "investigation":
        return False
    if result.get("status") != "EVIDENCE_RANKED_NOT_CAUSAL":
        return False
    if result.get("executable") is not True:
        return False
    if result.get("causal_claim") is not False:
        return False

    discovery = result.get("driver_discovery", {})
    evaluation = result.get("hypothesis_evaluation", {})

    if not isinstance(discovery, dict) or not isinstance(evaluation, dict):
        return False
    if discovery.get("status") != "RECONCILED_COMPONENT_BREAKDOWN":
        return False
    if evaluation.get("premise_confirmed") is not True:
        return False
    if evaluation.get("causal_claim") is not False:
        return False

    hypotheses = evaluation.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        return False

    supported = any(
        isinstance(h, dict)
        and h.get("hypothesis_id")
            == "financial_component:marketing_cost_effective"
        and h.get("disposition") == "SUPPORTS_PROFIT_PRESSURE"
        for h in hypotheses
    )
    if not supported:
        return False

    try:
        periods(result)
        before, after = accounting(result)
        return after - before > Decimal("0.02")
    except (MarketingRejected, KeyError, TypeError, ValueError):
        return False


def compile_plan(result):
    if not eligible(result):
        raise MarketingRejected("Marketing follow-up not justified")

    b0, b1, a0, a1 = periods(result)

    def window(start, end):
        return f"CAST(date AS DATE) >= DATE '{start}' AND CAST(date AS DATE) < DATE '{end}'"

    before = window(b0, b1)
    after = window(a0, a1)

    sql = f"""
SELECT COALESCE(jsonb_agg(to_jsonb(t)), '[]'::jsonb) AS campaigns
FROM (
    SELECT campaign_id,
        SUM(CASE WHEN {before} THEN spend ELSE 0 END)
            AS before_spend,
        SUM(CASE WHEN {after} THEN spend ELSE 0 END)
            AS after_spend,
        SUM(CASE WHEN {before} THEN 1 ELSE 0 END)
            AS before_rows,
        SUM(CASE WHEN {after} THEN 1 ELSE 0 END)
            AS after_rows,
        COUNT(DISTINCT CASE WHEN {before} THEN date END)
            AS before_dates,
        COUNT(DISTINCT CASE WHEN {after} THEN date END)
            AS after_dates
    FROM marketing.spend_daily
    WHERE ({before}) OR ({after})
    GROUP BY campaign_id
    ORDER BY campaign_id
) t
"""
    return {"periods": [[b0, b1], [a0, a1]], "sql": sql}


def count(row, field):
    value = row.get(field)
    if value is None or isinstance(value, bool):
        raise MarketingRejected("Missing campaign-day count")
    try:
        number = Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise MarketingRejected("Invalid campaign-day count") from exc
    if (
        not number.is_finite()
        or number != number.to_integral_value()
        or not 0 <= number <= 1000000
    ):
        raise MarketingRejected("Invalid campaign-day count")
    return int(number)


@retain_validated
def validate(result, plan, response):
    if plan != compile_plan(result):
        raise MarketingRejected("Marketing plan changed")

    if (
        not isinstance(response, dict)
        or not isinstance(response.get("rows"), list)
        or len(response["rows"]) != 1
        or not isinstance(response["rows"][0], dict)
    ):
        raise MarketingRejected("Expected one aggregate row")

    campaigns = response["rows"][0].get("campaigns")
    if not isinstance(campaigns, list) or not 1 <= len(campaigns) <= 128:
        raise MarketingRejected("Invalid campaign population")

    totals = [Decimal("0"), Decimal("0")]
    covered = [0, 0]
    ids = set()
    verified = []

    for raw in campaigns:
        if not isinstance(raw, dict):
            raise MarketingRejected("Invalid campaign evidence")

        cid = raw.get("campaign_id")
        if (
            not isinstance(cid, str)
            or not 1 <= len(cid) <= 128
            or cid in ids
        ):
            raise MarketingRejected("Duplicate or invalid campaign ID")
        ids.add(cid)

        values = [money(raw.get(k)) for k in
                  ("before_spend", "after_spend")]
        rows = [count(raw, k) for k in
                ("before_rows", "after_rows")]
        dates = [count(raw, k) for k in
                 ("before_dates", "after_dates")]

        for i in range(2):
            if dates[i] != rows[i]:
                raise MarketingRejected("Duplicate campaign-day keys")
            if rows[i] == 0 and values[i] != 0:
                raise MarketingRejected("Spend without dated records")
            totals[i] += values[i]
            covered[i] += rows[i]

        verified.append({
            "campaign_id": cid,
            "before_spend": str(values[0]),
            "after_spend": str(values[1]),
            "change": str(values[1] - values[0]),
            "campaign_day_rows": rows,
        })

    expected = accounting(result)

    if any(
        abs(totals[i] - expected[i]) > Decimal("0.02")
        for i in range(2)
    ):
        raise MarketingRejected(
            "Campaign spend contradicts finance accounting"
        )

    if min(covered) == 0:
        raise MarketingRejected("Missing comparison-period coverage")

    verified.sort(
        key=lambda x: (-Decimal(x["change"]), x["campaign_id"])
    )

    delta = totals[1] - totals[0]

    return {
        "evidence_id": (
            f"marketing-composition:{plan['periods'][0][0]}:"
            f"{plan['periods'][1][0]}"
        ),
        "status": "DESCRIPTIVE_RECONCILED",
        "source": "marketing.spend_daily",
        "periods": plan["periods"],
        "before_spend": str(totals[0]),
        "after_spend": str(totals[1]),
        "spend_change": str(delta),
        "campaign_day_rows": covered,
        "campaigns": verified,
        "causal_claim": False,
        "independent_mechanism_verified": False,
        "conclusion": (
            f"Recorded marketing spend increased by {delta}. "
            "Campaign-level movements reconcile to the financial "
            "marketing component, but do not establish campaign "
            "incrementality or an operational cause."
        ),
        "limitations": [
            "Marketing records are synthetic and may share the "
            "same generating process as the financial accounting.",
            "Campaign-day presence does not certify complete "
            "calendar coverage.",
            "Supplier costs, campaign incrementality and causal "
            "mechanisms remain independently unverified.",
        ],
    }


async def analyze(result, reader):
    plan = compile_plan(result)
    response = await reader(
        plan["sql"],
        "Governed descriptive campaign composition",
    )
    # The governed MCP reader may return the decoded single row directly.
    # Normalize that known transport shape; do not relax validation.
    if isinstance(response, dict) and set(response) == {"campaigns"}:
        response = {"rows": [response]}
    return validate(result, plan, response)
