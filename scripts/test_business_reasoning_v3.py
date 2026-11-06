
import asyncio
import json

from agent.business_reasoning import (
    _question_intent,
    add_business_reasoning,
)


async def fake_gemini(prompt, payload):
    data = json.loads(payload)
    assert data["aggregates"]

    return json.dumps({
        "business_significance": [
            "The observed financial movements show that additional sales did not translate into higher contribution profit. This makes the relationship between revenue and costs especially important for management."
        ],
        "possible_explanations": [
            "A shift toward lower-margin orders could produce this pattern, but product mix has not been established as the underlying cause."
        ],
        "recommended_checks": [
            "Examine reconciled cost components first, then investigate whether order economics changed through pricing, cost intensity or sales composition."
        ],
        "maintenance_actions": [
            "Monitor contribution margin alongside revenue rather than evaluating revenue growth in isolation."
        ],
        "caveat":
            "Accounting relationships explain recorded profit movements but do not establish the operational events responsible."
    })


def test_intent():
    assert _question_intent(
        "Why did revenue increase but profit decrease?"
    ) == "DIAGNOSTIC"

    assert _question_intent(
        "What was the late delivery rate?"
    ) == "METRIC_LOOKUP"


def test_financial_reasoning():
    record = {
        "executable": True,
        "causal_claim": False,
        "premise": {
            "divergence_confirmed": True,
            "revenue_delta": 139034.73,
            "contribution_profit_delta": -48578.13,
        },
    }

    original = deepcopy_record(record)

    result = asyncio.run(
        add_business_reasoning(
            "Why did revenue increase but profit decrease?",
            record,
            fake_gemini,
        )
    )

    assert result["business_reasoning_status"] == "GENERATED"
    assert result["business_reasoning"]["version"] == (
        "opslens.business_reasoning.v3"
    )
    assert result["premise"] == original["premise"]
    assert record == original


def deepcopy_record(record):
    return json.loads(json.dumps(record))


def test_provider_failure_preserves_result():
    async def failing_model(prompt, payload):
        raise RuntimeError("Simulated provider failure")

    record = {
        "executable": True,
        "causal_claim": False,
        "premise": {
            "divergence_confirmed": True,
            "revenue_delta": 139034.73,
            "contribution_profit_delta": -48578.13,
        },
    }

    result = asyncio.run(
        add_business_reasoning(
            "Explain this result",
            record,
            failing_model,
        )
    )

    assert result["business_reasoning_status"] == "PROVIDER_UNAVAILABLE"
    assert result["premise"] == record["premise"]
