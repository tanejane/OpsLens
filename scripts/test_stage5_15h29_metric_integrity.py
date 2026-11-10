
"""Synthetic regression tests for the H.28 shadow metric-integrity module."""

import unittest
from copy import deepcopy

from agent.refund_metric_integrity import assess


PERIOD = ["2018-01-01", "2018-02-01"]


def fixture():
    population = {
        "orders": 100,
        "returned_orders": 12,
        "refunded_orders": 10,
        "events": 13,
        "refund_amount": "500.00",
        "return_rate_pct": "12",
        "refund_rate_pct": "10",
    }

    initial = {
        "evidence_id": "returns:2018-01-01:2018-02-01",
        "period": PERIOD[:],
        "source": "commerce.orders + cx.returns",
        "causal_claim": False,
        "population": deepcopy(population),
    }

    detail = {
        "evidence_id": "refund-concentration:2018-01-01:2018-02-01",
        "period": PERIOD[:],
        "source": (
            "commerce.orders + cx.returns + commerce.order_items"
        ),
        "causal_claim": False,
        "population": deepcopy(population),
        "sellers": [
            {
                "seller_id": "A",
                "refund_amount": "300.00",
                "returned_orders": 7,
                "orders": 40,
            },
            {
                "seller_id": "B",
                "refund_amount": "100.00",
                "returned_orders": 3,
                "orders": 30,
            },
        ],
    }

    return {
        "route": "refund_concentration",
        "executable": True,
        "causal_claim": False,
        "evidence": initial,
        "refund_analysis": detail,
        "validated_evidence": [
            {
                "producer": "agent.refund_concentration.validate_initial",
                "result": deepcopy(initial),
            },
            {
                "producer": "agent.refund_concentration.validate_detail",
                "result": deepcopy(detail),
            },
        ],
    }


def mirror_initial(result):
    result["validated_evidence"][0]["result"] = deepcopy(
        result["evidence"]
    )


def mirror_detail(result):
    result["validated_evidence"][1]["result"] = deepcopy(
        result["refund_analysis"]
    )


class MetricIntegrityTests(unittest.TestCase):

    def check(self, result, metric, expected):
        observed = assess(result, PERIOD, metric)

        self.assertEqual(
            observed["status"] == "INTEGRITY_AND_RETAINED_MATCH",
            expected,
            observed,
        )
        self.assertIs(observed["execution_authorized"], False)
        self.assertIs(observed["completion_authorized"], False)
        self.assertIs(
            observed["source_provenance_authenticated"], False
        )
        self.assertIs(
            observed["original_validator_reexecuted"], False
        )

    # Positive baseline cases

    def test_valid_refund_rate(self):
        self.check(fixture(), "refund_rate", True)

    def test_valid_return_rate(self):
        self.check(fixture(), "return_rate", True)

    def test_valid_refunded_order_count(self):
        self.check(fixture(), "refunded_order_count", True)

    def test_valid_returned_order_count(self):
        self.check(fixture(), "returned_order_count", True)

    def test_valid_refund_amount(self):
        self.check(fixture(), "refund_amount", True)

    def test_valid_seller_ranking(self):
        self.check(fixture(), "seller_refund_ranking", True)

    # Mirrored errors that retained equality alone can miss

    def test_mirrored_incorrect_refund_rate(self):
        result = fixture()
        result["evidence"]["population"]["refund_rate_pct"] = "90"
        mirror_initial(result)
        self.check(result, "refund_rate", False)

    def test_mirrored_incorrect_return_rate(self):
        result = fixture()
        result["evidence"]["population"]["return_rate_pct"] = "80"
        mirror_initial(result)
        self.check(result, "return_rate", False)

    def test_mirrored_reversed_ranking(self):
        result = fixture()
        result["refund_analysis"]["sellers"].reverse()
        mirror_detail(result)
        self.check(result, "seller_refund_ranking", False)

    def test_invalid_population_bounds(self):
        result = fixture()
        result["evidence"]["population"]["returned_orders"] = 120
        mirror_initial(result)
        self.check(result, "seller_refund_ranking", False)

    def test_duplicate_seller(self):
        result = fixture()
        result["refund_analysis"]["sellers"][1]["seller_id"] = "A"
        mirror_detail(result)
        self.check(result, "seller_refund_ranking", False)

    def test_seller_total_exceeds_population(self):
        result = fixture()
        result["refund_analysis"]["sellers"][0]["refund_amount"] = "600"
        mirror_detail(result)
        self.check(result, "seller_refund_ranking", False)

    # Missing or invalid evidence

    def test_missing_seller_proof(self):
        result = fixture()
        result["validated_evidence"].pop()
        self.check(result, "seller_refund_ranking", False)

    def test_nonexecutable_record(self):
        result = fixture()
        result["executable"] = False
        self.check(result, "refund_rate", False)

    def test_missing_initial_proof(self):
        result = fixture()
        result["validated_evidence"].pop(0)
        self.check(result, "refund_rate", False)

    def test_unsupported_metric(self):
        self.check(fixture(), "customer_lifetime_value", False)

    def test_wrong_period(self):
        result = fixture()
        assessment = assess(
            result,
            ["2018-02-01", "2018-03-01"],
            "refund_rate",
        )
        self.assertEqual(
            assessment["status"], "NOT_DEMONSTRATED"
        )
        self.assertIs(assessment["execution_authorized"], False)

    # Numeric edge cases

    def test_nan_rejected(self):
        result = fixture()
        result["evidence"]["population"]["refund_rate_pct"] = "NaN"
        mirror_initial(result)
        self.check(result, "refund_rate", False)

    def test_infinity_rejected(self):
        result = fixture()
        result["evidence"]["population"]["refund_amount"] = "Infinity"
        mirror_initial(result)
        self.check(result, "refund_amount", False)

    def test_boolean_count_rejected(self):
        result = fixture()
        result["evidence"]["population"]["orders"] = True
        mirror_initial(result)
        self.check(result, "refund_rate", False)

    def test_zero_denominator_not_demonstrated(self):
        result = fixture()
        pop = result["evidence"]["population"]
        pop.update({
            "orders": 0,
            "returned_orders": 0,
            "refunded_orders": 0,
            "events": 0,
            "refund_amount": "0",
            "refund_rate_pct": None,
            "return_rate_pct": None,
        })
        mirror_initial(result)
        self.check(result, "refund_rate", False)

    def test_valid_precision(self):
        result = fixture()
        pop = result["evidence"]["population"]
        pop.update({
            "orders": 3,
            "returned_orders": 2,
            "refunded_orders": 1,
            "events": 2,
            "refund_amount": "5.00",
            "refund_rate_pct": "33.33333333333333333333333333",
            "return_rate_pct": "66.66666666666666666666666667",
        })
        mirror_initial(result)
        self.check(result, "refund_rate", True)

    def test_small_rate_mismatch_rejected(self):
        result = fixture()
        result["evidence"]["population"]["refund_rate_pct"] = "10.01"
        mirror_initial(result)
        self.check(result, "refund_rate", False)

    # Seller ordering: amount, returned-order count, seller ID

    def test_valid_seller_tie(self):
        result = fixture()
        sellers = result["refund_analysis"]["sellers"]
        sellers[0]["refund_amount"] = "200.00"
        sellers[1]["refund_amount"] = "200.00"
        mirror_detail(result)
        self.check(result, "seller_refund_ranking", True)

    def test_incorrect_seller_tie_order(self):
        result = fixture()
        sellers = result["refund_analysis"]["sellers"]
        sellers[0]["refund_amount"] = "200.00"
        sellers[1]["refund_amount"] = "200.00"
        sellers.reverse()
        mirror_detail(result)
        self.check(result, "seller_refund_ranking", False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
