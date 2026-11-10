"""Proof-backed descriptive question coverage.

Standalone evaluation only. Does not execute tools or modify routing.
The retained archive provides consistency evidence, not authentication.
"""

from copy import deepcopy


ADAPTERS = {
    "monthly_returns": {
        "field": "evidence",
        "producer": "agent.refund_concentration.validate_initial",
        "source": "commerce.orders + cx.returns",
        "kind": "returns",
    },
    "refund_sellers": {
        "field": "refund_analysis",
        "producer": "agent.refund_concentration.validate_detail",
        "source": "commerce.orders + cx.returns + commerce.order_items",
        "kind": "sellers",
    },
    "late_delivery": {
        "field": "evidence",
        "producer": "agent.phase4c15_delivery.validate_metric",
        "source": "semantic.order_delivery_evidence_v1",
        "kind": "delivery",
    },
    "delivery_sellers": {
        "field": "seller_analysis",
        "producer": "agent.seller_concentration.validate",
        "source": "semantic.order_delivery_evidence_v1 + commerce.order_items",
        "kind": "sellers",
    },
}


def _valid_shape(proof, kind):
    if not isinstance(proof, dict):
        return False

    population = proof.get("population")
    if not isinstance(population, dict):
        return False

    if kind == "sellers":
        return (
            isinstance(proof.get("sellers"), list)
            and len(proof["sellers"]) > 0
            and isinstance(proof.get("evidence_id"), str)
            and bool(proof["evidence_id"])
        )

    if kind == "returns":
        required = ("orders", "returned_orders", "events")
        if not all(type(population.get(k)) is int for k in required):
            return False

        orders = population["orders"]
        returned = population["returned_orders"]
        events = population["events"]

        return (
            orders > 0
            and 0 <= returned <= orders
            and events >= returned
        )

    if kind == "delivery":
        if proof.get("metric_id") != "late_delivery_rate":
            return False

        required = ("lateness_eligible_orders", "late_orders")
        if not all(type(population.get(k)) is int for k in required):
            return False

        eligible = population["lateness_eligible_orders"]
        late = population["late_orders"]

        return eligible > 0 and 0 <= late <= eligible

    return False


def verify(response, adapter_id, period):
    """Return a proof reference only for an exact unique retained match."""
    adapter = ADAPTERS.get(adapter_id)

    if adapter is None:
        return None

    if not isinstance(response, dict):
        return None

    if response.get("executable") is not True:
        return None

    if response.get("causal_claim") is not False:
        return None

    proof = response.get(adapter["field"])

    if not isinstance(proof, dict):
        return None

    if (
        proof.get("period") != list(period)
        or proof.get("source") != adapter["source"]
        or proof.get("causal_claim") is not False
        or not _valid_shape(proof, adapter["kind"])
    ):
        return None

    archive = response.get("validated_evidence")

    if not isinstance(archive, list):
        return None

    matches = [
        i
        for i, entry in enumerate(archive)
        if isinstance(entry, dict)
        and entry.get("producer") == adapter["producer"]
        and entry.get("result") == proof
    ]

    if len(matches) != 1:
        return None

    index = matches[0]

    return {
        "adapter": adapter_id,
        "producer": adapter["producer"],
        "evidence_ref": "/payload/" + adapter["field"],
        "retained_ref": (
            f"/payload/validated_evidence/{index}/result"
        ),
    }


def evaluate(response, period, requirements):
    """Evaluate an explicit requirement-to-adapter mapping.

    Unknown adapters are NOT_EVALUATED, never silently satisfied.
    Requirement extraction is outside this contract.
    """
    if (
        not isinstance(requirements, dict)
        or not requirements
        or not isinstance(period, (list, tuple))
        or len(period) != 2
        or not all(isinstance(x, str) for x in period)
    ):
        raise ValueError("Invalid coverage specification")

    results = []

    for name, adapter_id in requirements.items():
        if not isinstance(name, str) or not name:
            raise ValueError("Invalid requirement identifier")

        if adapter_id not in ADAPTERS:
            results.append({
                "requirement": name,
                "adapter": adapter_id,
                "state": "NOT_EVALUATED",
                "proof": None,
                "reason": "No registered evidence adapter",
            })
            continue

        proof = verify(response, adapter_id, period)

        results.append({
            "requirement": name,
            "adapter": adapter_id,
            "state": "SATISFIED" if proof else "UNVERIFIED",
            "proof": proof,
            "reason": (
                "Exact retained validator output matched"
                if proof else
                "Required validated evidence was not demonstrated"
            ),
        })

    satisfied = sum(
        item["state"] == "SATISFIED" for item in results
    )

    if satisfied == len(results):
        decision = "COMPLETE_DESCRIPTIVE"
    elif satisfied:
        decision = "PARTIAL_EVIDENCE"
    else:
        decision = "NOT_DEMONSTRATED"

    return {
        "contract": "opslens.evidence-coverage.v1",
        "decision": decision,
        "requirements_satisfied": satisfied,
        "requirements_total": len(results),
        "evaluation_complete": all(
            item["state"] != "NOT_EVALUATED"
            for item in results
        ),
        "requirements": deepcopy(results),
        "causal_mechanism_verified": False,
        "limitations": [
            "Requirements are explicitly supplied, not automatically parsed.",
            "Proof matching checks response consistency, not independent authenticity.",
            "Descriptive completion does not establish causal attribution.",
        ],
    }
