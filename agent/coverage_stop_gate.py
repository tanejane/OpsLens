"""Strict opt-in, proof-backed completion stop gate.

Only exact registered benchmark questions are eligible.
Does not execute tools, replan, or modify retained evidence.
"""

from copy import deepcopy
from hashlib import sha256

from agent.completion_policy import recommend


REGISTRY = {
    'ccfe37594b9343ef6adc5d27134f16373daa76866dd2d09dfa0fdd932cf0b1e2': {
        "case": "INC_003",
        "route": "refund_concentration",
        "period": ("2018-01-01", "2018-02-01"),
        "requirements": {
            "monthly_returns": "monthly_returns",
            "seller_concentration": "refund_sellers",
            "product_concentration": None,
            "spike_vs_baseline": None,
        },
    },
    '1972dcb39f1638e3c10d67fd4dc3ff5efaf979bf37bce7f525da753741db442a': {
        "case": "INC_004",
        "route": "seller_concentration",
        "period": ("2018-08-01", "2018-09-01"),
        "requirements": {
            "late_delivery": "late_delivery",
            "seller_concentration": "delivery_sellers",
        },
    },
}


def apply_gate(question, response):
    """Return the original response unless strict eligibility holds."""
    if not isinstance(question, str) or not isinstance(response, dict):
        return response

    fingerprint = sha256(question.encode("utf-8")).hexdigest()
    spec = REGISTRY.get(fingerprint)

    if spec is None:
        return response

    orchestration = response.get("orchestration")

    if not isinstance(orchestration, dict):
        return response

    original_stop = orchestration.get("stop_reason")

    # Never replace safety failures, budget stops or other decisions.
    if (
        original_stop != "QUESTION_ADDRESSED"
        or response.get("route") != spec["route"]
        or response.get("executable") is not True
        or response.get("causal_claim") is not False
    ):
        return response

    updated = deepcopy(response)
    updated_orchestration = updated["orchestration"]

    try:
        policy = recommend(
            response,
            {
                "period": spec["period"],
                "requirements": spec["requirements"],
            },
        )

        proposed = policy["decision"]

        # Advisory policy cannot upgrade the original result.
        permitted = {
            "QUESTION_ADDRESSED",
            "QUESTION_PARTIALLY_ADDRESSED",
            "QUESTION_NOT_DEMONSTRATED",
        }

        if proposed not in permitted:
            raise ValueError("Unsupported completion decision")

        updated["coverage_assessment"] = {
            "mode": "strict_exact_question_pilot",
            "case": spec["case"],
            "policy": policy,
        }

        updated_orchestration["original_stop_reason"] = original_stop
        updated_orchestration["coverage_gate_enabled"] = True
        updated_orchestration["stop_reason"] = proposed

        if proposed != "QUESTION_ADDRESSED":
            limitation = (
                "The original coordinator completed its available "
                "execution path, but proof-backed question coverage "
                "is incomplete. See coverage_assessment for gaps."
            )
            updated["limitations"] = [
                *(updated.get("limitations") or []),
                limitation,
            ]

            # Make unresolved requirements visible in the
            # existing deterministic explanation.
            unresolved = [
                item
                for item in policy["coverage"]["requirements"]
                if item["state"] != "SATISFIED"
            ]

            labels = {
                "product_concentration":
                    "product-level return concentration",
                "spike_vs_baseline":
                    "comparison against a suitable baseline",
            }

            details = "; ".join(
                labels.get(
                    item["requirement"],
                    item["requirement"].replace("_", " "),
                ) + " (" + item["state"] + ")"
                for item in unresolved
            )

            coverage_text = (
                "The investigation is only partially addressed. "
                "Unresolved requirements: " + details + ". "
                "The existing validated findings remain descriptive; "
                "these additional analyses have not been verified."
            )

            explanation = updated.get("explanation")

            if isinstance(explanation, dict):
                sections = explanation.get("sections")

                if isinstance(sections, list):
                    sections.append({
                        "kind": "limitation",
                        "text": coverage_text,
                        "evidence_refs": [
                            "/payload/coverage_assessment/"
                            "policy/coverage/requirements"
                        ],
                        "causal_claim": False,
                        "coverage_contract":
                            "opslens.evidence-coverage.v1",
                    })

    except Exception as exc:
        # A coverage-evaluation failure cannot certify completion.
        updated_orchestration["original_stop_reason"] = original_stop
        updated_orchestration["coverage_gate_enabled"] = True
        updated_orchestration["stop_reason"] = (
            "COVERAGE_EVALUATION_FAILED"
        )
        updated["coverage_assessment"] = {
            "mode": "strict_exact_question_pilot",
            "case": spec["case"],
            "decision": "COVERAGE_EVALUATION_FAILED",
            "error_type": type(exc).__name__,
        }
        updated["limitations"] = [
            *(updated.get("limitations") or []),
            "The completion coverage check failed and therefore "
            "cannot certify that the question was fully addressed.",
        ]

    return updated
