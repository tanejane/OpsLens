
import asyncio

from agent.phase5_3c_incident_gateway import (
    identify,
    is_finance_bridge,
    _finance_retry_candidate,
    repair,
)


WHY = (
    "Why did revenue increase but contribution profit "
    "decrease from February to March 2018?"
)

COMPARE = (
    "Compare revenue, contribution profit, and cost of goods "
    "sold between February 2018 and March 2018. "
    "Identify the largest recorded accounting contributions "
    "to the profit movement."
)

GAP = {
    "route": "investigation_planner",
    "status": "ACTIONABLE_EVIDENCE_GAP",
    "executable": False,
    "causal_claim": False,
}


def verified_result():
    return {
        "route": "investigation",
        "status": "MEASURED_WITH_LIMITATIONS",
        "executable": True,
        "causal_claim": False,
        "periods": {
            "before": ["2018-02-01", "2018-03-01"],
            "after": ["2018-03-01", "2018-04-01"],
        },
    }


def test_questions_are_recognized():
    why_plan = identify(WHY)
    compare_plan = identify(COMPARE)

    assert is_finance_bridge(WHY, why_plan)
    assert _finance_retry_candidate(WHY, why_plan)
    assert _finance_retry_candidate(COMPARE, compare_plan)


def test_existing_gap_can_recover():
    calls = []

    async def investigator(question, reader):
        calls.append(question)
        return verified_result()

    for question in (WHY, COMPARE):
        result = asyncio.run(
            repair(question, dict(GAP), investigator, None)
        )
        assert result["executable"] is True
        assert (
            result["investigation_gateway"]["status"]
            == "GOVERNED_FINANCE_RETRY"
        )

    assert len(calls) == 2
    assert calls[0].startswith("Why did")
    assert calls[1].startswith("Compare")


def test_failed_retry_preserves_evidence_gap():
    async def unsupported(question, reader):
        return {
            "route": "investigation",
            "status": "NOT_SUPPORTED",
            "executable": False,
            "causal_claim": False,
        }

    result = asyncio.run(
        repair(WHY, dict(GAP), unsupported, None)
    )
    assert result == GAP


def test_completed_evidence_is_never_overridden():
    async def should_not_run(question, reader):
        raise AssertionError("Unexpected retry")

    original = verified_result()

    result = asyncio.run(
        repair(WHY, original, should_not_run, None)
    )

    assert result == original


def test_wrong_periods_cannot_be_accepted():
    async def wrong_period(question, reader):
        result = verified_result()
        result["periods"]["after"] = [
            "2018-04-01", "2018-05-01"
        ]
        return result

    result = asyncio.run(
        repair(WHY, dict(GAP), wrong_period, None)
    )

    assert result == GAP
