"""Static business possibilities, never observed evidence or execution authority."""

# Each check states both supporting and weakening observations. No fixture truth.
OPTIONS = {
    'finance': (
        'Higher unit input costs, a different sales mix, or higher variable charges could reduce profit despite revenue growth.',
        'Comparable product quantities and realized prices, effective-dated purchase costs, and reconciled charge components.',
        'First reconcile the existing revenue/COGS/charge bridge. Compare the same products and quantities across periods: higher matched unit costs support cost pressure; stable costs weaken it. Reconcile residuals before attributing them.'),
    'product_mix': (
        'A shift toward lower-margin products could dilute aggregate margin.',
        'Item quantities, realized prices and governed item-level cost allocations for both periods.',
        'Compare category sales shares, then hold mix constant using reconciled item margins. Stable shares or margins weaken a mix explanation; changed shares alone do not prove profit impact.'),
    'returns_quality': (
        'Product defects, fulfillment problems or changes in return eligibility could increase refunds.',
        'Return reasons, comparable observation windows, item-level return linkage and quality inspection records.',
        'Compare return rates within matched products and observation windows. Concentrated defect reasons support a quality hypothesis; stable matched rates or policy changes weaken it. Do not allocate order refunds to individual items without linkage.'),
    'delivery': (
        'Capacity constraints or a change in destination mix could worsen delivery performance.',
        'Handoff timestamps, carrier and destination linkage, promised service levels and capacity logs.',
        'Compare lateness within the same carrier, destination and service level. Longer handoff times support a capacity hypothesis; stable within-group performance suggests checking composition instead.'),
    'satisfaction': (
        'Delivery delays, product quality or a change in who submits reviews could change average ratings.',
        'Order-linked delivery and review outcomes, review coverage, product details and feedback reasons.',
        'Use the existing late/on-time review comparison and inspect review coverage. Within-product rating differences support further investigation; similar ratings or changing response coverage weaken a delivery explanation. Association is not causation.'),
    'inventory': (
        'Reduced availability could suppress observed sales, but weaker demand could also explain lower sales.',
        'Product-day availability, replenishment timing and an independent demand comparison.',
        'Compare available and unavailable periods against comparable products and seasonality. A decline confined to unavailable periods supports further checks; similar declines among available products weaken the stockout hypothesis.'),
    'regional': (
        'Regional demand composition or fulfillment capacity could change recognized revenue.',
        'Region-linked orders, cancellation reasons, capacity logs and comparable demand measures.',
        'Compare regional outcomes within comparable products and periods. Capacity breaches aligned with cancellations support further checks; unchanged capacity and cancellation rates weaken that hypothesis.'),
    'documents': (
        'Cost recognition timing or a revised source document could explain an apparent discrepancy.',
        'Versioned invoices, accrual periods, source precedence and ledger reconciliation.',
        'Reconcile service periods and document versions to recorded charges. Timing-aligned differences support a recognition explanation; matching periods and values weaken it. A document assertion alone is not proof.'),
    'confounding': (
        'Differences in customer or order composition could create an aggregate association.',
        'Exposure definitions, temporal ordering, comparable groups and relevant pre-exposure strata.',
        'Compare outcomes within pre-exposure strata. A disappearing or reversing association supports confounding concerns; persistence alone still does not establish a causal effect.'),
}


def suggestions(domains):
    """Bounded deterministic fallback; does not echo user/model content."""
    return [dict(hypothesis_id=domain, status='UNVERIFIED_HYPOTHESIS',
                 basis='general_business_knowledge_not_case_evidence', causal_claim=False,
                 hypothesis=OPTIONS[domain][0], missing_evidence=OPTIONS[domain][1],
                 next_check=OPTIONS[domain][2])
            for domain in dict.fromkeys(domains) if domain in OPTIONS][:3]
