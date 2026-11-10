"""Conservative, non-executable requirement identification.

No SQL, tool permissions, evidence verification, or stop-policy changes.
Unknown scope is explicitly rejected or left unclassified.
"""

import re
from calendar import month_name

MONTHS = {
    name.lower(): i
    for i, name in enumerate(month_name)
    if i
}

MONTH_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{4})\b",
    re.I,
)

MONTH_ONLY_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\b",
    re.I,
)

REGISTRY = {
    "monthly_returns",
    "refund_sellers",
    "late_delivery",
    "delivery_sellers",
}


def _result(status, intent=None, requirements=(),
            period=(), reason=""):
    return {
        "contract": "opslens.requirement-extraction.v1",
        "status": status,
        "intent": intent,
        "requirements": list(requirements),
        "period_labels": list(period),
        "registered_adapters": {
            item: item if item in REGISTRY else None
            for item in requirements
        },
        "reason": reason,
        "execution_authorized": False,
        "evidence_state": "NOT_ASSESSED",
    }


def extract(question):
    if not isinstance(question, str) or not question.strip():
        return _result("ABSTAIN", reason="Empty or invalid question")

    q = " ".join(question.lower().split())

    # Security classification takes precedence over business keywords.
    guidance = (
        re.search(r"\b(untrusted|vendor document|vendor note)\b", q)
        and re.search(r"\b(how should|what should|handled|treat)\b", q)
        and re.search(r"\b(instruct|reveal|ignore|approve|write|secrets?)\b", q)
    )

    if guidance:
        return _result(
            "SECURITY_GUIDANCE",
            "security_guidance",
            (
                "untrusted_instruction_recognition",
                "no_secret_disclosure",
                "no_financial_write_approval",
                "safe_evidence_handling",
            ),
            reason="Untrusted instructions require non-executable guidance",
        )

    if (
        re.search(r"\b(ignore (?:the |all )?safeguards|"
                  r"ignore (?:the |all )?rules|"
                  r"ignore (?:the |all )?(?:previous |prior )?instructions|"
                  r"disregard (?:previous |prior |system )instructions|"
                  r"reveal (?:hidden|system) instructions)\b", q)
        or (
            re.search(r"\b(authori[sz]e|approve|execute)\b", q)
            and re.search(r"\b(financial|database)\b", q)
            and re.search(r"\bwrite\b", q)
        )
    ):
        return _result(
            "UNAUTHORIZED_ACTION",
            "unauthorized_action",
            ("reject_unapproved_write",),
            reason="Question requests an unauthorized action",
        )

    # Mixed-domain questions require a separate validated parser.
    if re.search(
        r"\b(invoice|invoices|accrual|accruals|"
        r"fulfillment|fulfilment|supplier)\b", q
    ):
        return _result(
            "ABSTAIN",
            reason="Cross-domain analytical scope not registered",
        )

    periods = MONTH_RE.findall(q)

    if len(periods) != 1:
        if MONTH_ONLY_RE.search(q) and not periods:
            return _result(
                "CLARIFICATION_REQUIRED",
                reason="Purchase year is unspecified",
            )

        return _result(
            "ABSTAIN",
            reason="Exactly one explicit month and year required",
        )

    month, year = periods[0]
    period = (f"{year}-{MONTHS[month.lower()]:02d}",)

    # Explicit population, geography, grouping or denominator
    # restrictions require separately registered evidence adapters.
    unsupported_scope = re.search(
        r"\bby\s+(?:customer\s+)?(?:segments?|regions?|"
        r"cities|city|states|product\s+categor(?:y|ies))\b"
        r"|\bfor\s+(?:vip|new|returning)\s+customers?\s+only\b"
        r"|\bfor\s+[a-z]{2}\s+only\b"
        r"|\bexcluding\b"
        r"|\bexcept\s+(?:for\s+)?(?:missing|unknown)\b"
        r"|\b(?:include|including)\s+only\b",
        q,
        re.I,
    )

    if unsupported_scope:
        return _result(
            "ABSTAIN",
            reason=(
                "Explicit analytical filter or denominator "
                "not supported by the registered extractor"
            ),
        )


    refund = bool(
        re.search(r"\b(refund\w*|return\w*)\b", q)
    )
    delivery = bool(
        re.search(r"\b(late|lateness|delay\w*|deliver\w*)\b", q)
    )

    promotion = bool(
        re.search(r"\b(promotion\w*|campaign\w*)\b", q)
    )
    causal = bool(
        re.search(r"\b(cause\w*|causal|responsib\w*)\b", q)
    )


    negated_causal = bool(
        re.search(
            r"\bnot\s+(?:the\s+)?(?:caus\w*|responsib\w*)\b",
            q,
        )
    )

    if negated_causal:
        # Remove explicitly negated causal phrases before
        # looking for an additional affirmative causal demand.
        affirmative_text = re.sub(
            r"\bnot\s+(?:the\s+)?(?:caus\w*|responsib\w*)\b",
            " ",
            q,
        )

        other_causal_request = bool(
            re.search(
                r"\b(?:caus\w*|responsib\w*)\b",
                affirmative_text,
            )
        )

        if other_causal_request:
            return _result(
                "ABSTAIN",
                reason=(
                    "Mixed negated and affirmative causal "
                    "language requires clarification"
                ),
            )

        causal = False

    seller = bool(
        re.search(r"\b(seller\w*|by seller)\b", q)
    )
    product = bool(
        re.search(r"\b(product\w*|sku\w*)\b", q)
    )
    spike = bool(
        re.search(r"\b(spike|increase|increased|rise|rose)\b", q)
    )

    if promotion and refund and causal:
        if re.search(r"\b(order[- ]value)\b", q):
            return _result(
                "EXTRACTED_UNSUPPORTED",
                "promotion_causality",
                (
                    "promotion_exposure_refund_comparison",
                    "order_value_stratification",
                    "confounding_assessment",
                    "causal_identification",
                ),
                period,
                "Causal requirements identified; adapters unavailable",
            )

        return _result(
            "ABSTAIN",
            reason="Causal adjustment specification incomplete",
        )

    if promotion:
        return _result(
            "ABSTAIN",
            reason="Promotion analysis not registered",
        )

    # A general request for refund associations does not identify
    # the variables or cohorts required for an association analysis.
    # A supported seller breakdown is a distinct descriptive request.
    if (
        refund
        and not delivery
        and not seller
        and not product
        and not promotion
        and re.search(
            r"\b(?:associations?|associated|correlations?)\b",
            q,
        )
    ):
        return _result(
            "ABSTAIN",
            reason=(
                "Refund association requires an explicit "
                "comparison dimension or population"
            ),
        )

    if refund and not delivery:
        if product and spike:
            return _result(
                "EXTRACTED_UNSUPPORTED",
                "refund_product_spike",
                (
                    "monthly_returns",
                    "product_concentration",
                    "spike_vs_baseline",
                ),
                period,
                "Product and baseline requirements lack registered adapters",
            )

        if product or causal or spike:
            return _result(
                "ABSTAIN",
                reason="Unsupported refund analytical requirement",
            )

        if seller:
            return _result(
                "EXTRACTED",
                "refund_seller_breakdown",
                ("monthly_returns", "refund_sellers"),
                period,
            )

        return _result(
            "EXTRACTED",
            "refund_measurement",
            ("monthly_returns",),
            period,
        )

    if delivery and not refund:
        if seller and causal:
            return _result(
                "EXTRACTED_UNSUPPORTED",
                "delivery_causality",
                (
                    "late_delivery",
                    "delivery_sellers",
                    "seller_causal_responsibility",
                ),
                period,
                "Seller association cannot establish responsibility",
            )

        if seller:
            return _result(
                "EXTRACTED",
                "delivery_seller_breakdown",
                ("late_delivery", "delivery_sellers"),
                period,
            )

        if causal:
            return _result(
                "ABSTAIN",
                reason="Causal delivery analysis not registered",
            )

        return _result(
            "EXTRACTED",
            "delivery_measurement",
            ("late_delivery",),
            period,
        )

    return _result(
        "ABSTAIN",
        reason="Question falls outside registered extraction patterns",
    )
