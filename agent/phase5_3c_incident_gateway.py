"""Phase 5.3C: failure-aware, bounded investigation planning.

This layer never accepts ground truth, generates SQL, grants writes, or asserts causal
mechanisms. It only repairs verified two-month finance requests via the existing
investigator and converts *failed* broad interpretations into explicit evidence gaps.
"""
from __future__ import annotations
from datetime import date
import re

MONTH_NAMES = ('January','February','March','April','May','June','July','August','September','October','November','December')
MONTH = re.compile(r'\b('+'|'.join(MONTH_NAMES)+r')\s+(20\d{2})\b',re.I)
SHARED = re.compile(r'\b(?:from|between)\s+('+'|'.join(MONTH_NAMES)+r')\s+(?:to|and)\s+('+'|'.join(MONTH_NAMES)+r')\s+(20\d{2})\b',re.I)
DANGEROUS = re.compile(r'(?:;\s*(?:drop|delete|update|insert|alter|grant|revoke)\b|/\*|\*/|--|\b(?:drop\s+table|delete\s+from|update\s+\w+\s+set|insert\s+into|alter\s+table|grant\s+\w+|revoke\s+\w+|ignore (?:all )?(?:previous|prior) instructions|ignore (?:all )?(?:rules|instructions))\b)',re.I)
FINANCE = re.compile(r'\b(?:revenue|profit|margin|cogs|marketing|refund|finance|financial|cost|spend|accrual|invoice)\b',re.I)
DIVERGENCE = re.compile(r'\b(?:profit|contribution profit)\b',re.I)
GROWTH = re.compile(r'\b(?:revenue|sales)\b',re.I)
CHANGE = re.compile(
    r'\b(?:grew|rose|increas(?:e|ed|es|ing)|up|'
    r'fell|decreas(?:e|ed|es|ing)|down|declin(?:e|ed|es|ing))\b',
    re.I,
)

CAPABILITIES = (
 ('inventory', r'\b(?:stockouts?|inventory|out[ -]of[ -]stock|availability)\b',
  ('inventory availability by product and date','lost-demand counterfactual or independently validated stockout model')),
 ('documents', r'\b(?:documents?|notes?|vendor note|supplier invoice|accrual|reviewed later|conflict|untrusted)\b',
  ('versioned source documents with trustworthy timestamps','source trust and precedence review')),
 ('regional', r'\b(?:region|regional|RJ|capacity|state[- ]level|seller state)\b',
  ('region-linked eligible orders and capacity logs','independently approved lost-order definition')),
 ('returns_quality', r'\b(?:returns?|refunds?|seller quality|defect|product quality)\b',
  ('order-level returns/refunds with eligibility rules','seller and product linkage with verified grain')),
 ('delivery', r'\b(?:delivery|deliveries|late[- ]deliver\w*|fulfill|carrier|delay)\b',
  ('governed delivery metrics for the requested period','approved seller/carrier linkage for attribution')),
 ('satisfaction', r'\b(?:reviews?|ratings?|satisfaction|customer experience)\b',
  ('governed review metrics and eligible denominators','independently validated order/seller linkage')),
 ('product_mix', r'\b(?:category mix|product mix|product categor|sku|category)\b',
  ('category item sales mix at item grain','category-level profitability and allocation reconciliation')),
 ('finance', r'\b(?:revenue|profit|margin|cogs|marketing|refund|spend|accrual|invoice)\b',
  ('approved finance metrics and cost breakdown','independent attribution source and modeled-cost validation')),
 ('confounding', r'\b(?:confound|strata|stratif|order.value|promotions? cause|correlation)\b',
  ('stratified cohort counts and outcomes','comparison within relevant confounder strata')),
)


def months_of(question):
    if not isinstance(question,str):return []
    found=[(int(y),next(i for i,n in enumerate(MONTH_NAMES,1) if n.lower()==m.lower())) for m,y in MONTH.findall(question)]
    if len(found) <= 1:
        match=SHARED.search(question)
        if match:
            a,b,y=match.groups();found=[(int(y),MONTH_NAMES.index(a.capitalize())+1),(int(y),MONTH_NAMES.index(b.capitalize())+1)]
    # Don't infer a year or silently discard extra months; ambiguity is visible.
    return [date(y,m,1).isoformat() for y,m in found]


def identify(question):
    if not isinstance(question,str) or len(question.strip())>800 or not question.strip():return None
    domains=[(name,requirements) for name,pattern,requirements in CAPABILITIES if re.search(pattern,question,re.I)]
    if not domains:return None
    return {'requested_months':months_of(question),'domains':[name for name,_ in domains],
            'evidence_requirements':list(dict.fromkeys(req for _,items in domains for req in items))}


def is_finance_bridge(question, plan):
    months = sorted(plan["requested_months"])

    if (
        len(months) != 2
        or len(set(months)) != 2
        or months[0] >= months[1]
        or DANGEROUS.search(question)
    ):
        return False

    if any(
        domain in plan["domains"]
        for domain in (
            "inventory",
            "documents",
            "regional",
            "confounding",
        )
    ):
        return False

    has_finance = bool(FINANCE.search(question))
    has_revenue = bool(GROWTH.search(question))
    has_profit = bool(DIVERGENCE.search(question))

    has_increase = bool(
        re.search(
            r"\b(?:grew|rose|increas(?:e|ed|es|ing)|up)\b",
            question,
            re.I,
        )
    )

    has_decrease = bool(
        re.search(
            r"\b(?:fell|decreas(?:e|ed|es|ing)|"
            r"down|declin(?:e|ed|es|ing))\b",
            question,
            re.I,
        )
    )

    return (
        has_finance
        and has_revenue
        and has_profit
        and has_increase
        and has_decrease
    )


def _safe_gap(question,previous,plan):
    from agent.business_hypotheses import suggestions
    missing=plan['evidence_requirements']
    return {'route':'investigation_planner','status':'ACTIONABLE_EVIDENCE_GAP','executable':False,
            'approved_for_mcp':False,'causal_claim':False,'inventory_claim_allowed':False,
            'requested_months':plan['requested_months'],'requested_domains':plan['domains'],
            'evidence_requirements':missing,'source_evidence':[],
            'unverified_hypotheses':suggestions(plan['domains']),
            'verified_mechanism':False,'next_step':'Obtain and validate required sources, then run a separately approved bounded analysis',
            'upstream':{'route':previous.get('route'),'status':previous.get('status'),
                       'reason':str(previous.get('reason',''))[:200],
                       'error_type':previous.get('error_type')},
            'limitations':['This is an evidence plan, not a completed investigation',
                           'No data source was queried by this gateway',
                           'No inventory, causal, source recency or join permission is inferred']}


def _next_month(month):
    day=date.fromisoformat(month)
    return date(day.year+1,1,1).isoformat() if day.month==12 else date(day.year,day.month+1,1).isoformat()


async def _approved_monthly_metrics(plan, reader):
    """Measured observations only: no seller joins, attribution, or inventory claims.

    Do not let an agent select arbitrary SQL; use existing bounded metric compilers.
    A failure in any requested measurement is returned as a gap, not partial proof.
    """
    months=plan['requested_months']
    if len(months)!=1 or any(x in plan['domains'] for x in
        ('inventory','documents','regional','confounding','finance','product_mix','returns_quality')):
        return None
    supported=[d for d in plan['domains'] if d in ('delivery','satisfaction')]
    if not supported:return None
    from agent.phase4c15_delivery import measure as delivery_measure
    from agent.phase4c11_satisfaction import measure as satisfaction_measure
    start=months[0];end=_next_month(start)
    observed=[]
    try:
        if 'delivery' in supported:
            observed.append(await delivery_measure('late_delivery_rate',start,end,reader))
        if 'satisfaction' in supported:
            observed.append(await satisfaction_measure('average_review_score',start,end,reader))
            observed.append(await satisfaction_measure('low_rating_rate',start,end,reader))
    except Exception:
        return None
    expected=[]
    if 'delivery' in supported: expected.append(('late_delivery_rate','semantic.order_delivery_evidence_v1'))
    if 'satisfaction' in supported: expected.extend([('average_review_score','semantic.order_review_evidence_v1'),
                                                  ('low_rating_rate','semantic.order_review_evidence_v1')])
    if len(observed)!=len(expected) or not all(
        isinstance(r,dict) and r.get('status')=='MEASURED_WITH_SCOPE_LIMITS'
        and r.get('causal_claim') is False and r.get('period')==[start,end]
        and r.get('metric_id')==metric and r.get('source')==source
        and isinstance(r.get('population'),dict) and isinstance(r.get('value'),str)
        for r,(metric,source) in zip(observed,expected)):
        return None
    return {'route':'investigation_planner','status':'PARTIAL_GOVERNED_EVIDENCE',
            'executable':True,'approved_for_mcp':False,'causal_claim':False,
            'inventory_claim_allowed':False,'requested_months':months,
            'requested_domains':plan['domains'],'observations':observed,
            'source_evidence':[{'source':r['source'],'period':r['period'],
                                'metric_id':r['metric_id'],'value':r['value'],
                                'unit':r['unit'],'population':r.get('population')}
                                for r in observed],
            'verified_mechanism':False,'scope':'monthly_descriptive_metrics_only',
            'next_step':'Require independently approved order/seller/carrier linkage to evaluate concentration or attribution',
            'limitations':['These aggregate metrics do not establish seller-level concentration',
                'Purchase-month cohort and metric-specific eligibility apply',
                'No approved new join or causal inference'],
            'tool_trace':[{'capability':'existing_governed_metric_compiler',
                           'source':r['source'],'metric_id':r['metric_id'],
                           'write_executed':False} for r in observed]}



def _finance_retry_candidate(question, plan):
    """Identify a bounded, two-month finance question.

    This only permits a retry through the existing governed
    investigator. It does not approve queries or prove causes.
    """
    months = sorted(plan.get("requested_months", []))
    domains = plan.get("domains", [])

    if (
        len(months) != 2
        or len(set(months)) != 2
        or months[0] >= months[1]
        or DANGEROUS.search(question)
    ):
        return False

    if any(
        domain in domains
        for domain in (
            "inventory",
            "documents",
            "regional",
            "confounding",
        )
    ):
        return False

    # Require an explicit revenue/profit financial comparison.
    if not (
        GROWTH.search(question)
        and DIVERGENCE.search(question)
    ):
        return False

    return bool(
        is_finance_bridge(question, plan)
        or re.search(
            r"\b(compare|comparison|between|from)\b",
            question,
            re.I,
        )
    )


async def repair(question, previous, finance_investigator, reader):
    """Recover supported evidence without overriding successful results."""

    if not isinstance(previous, dict):
        return previous

    # Never replace a completed governed result.
    if previous.get("executable") is True:
        return previous

    # Preserve intentional three-domain clarification refusals.
    if (
        previous.get("route") == "three_domain_investigation"
        and previous.get("status") == "NEEDS_CLARIFICATION"
    ):
        return previous

    plan = identify(question)

    if plan is None:
        return previous

    if DANGEROUS.search(question):
        return previous

    retry_finance = _finance_retry_candidate(question, plan)

    ordinary_recoverable = {
        "NEEDS_CLARIFICATION",
        "NOT_YET_SUPPORTED",
        "NOT_SUPPORTED",
        "MULTIDOMAIN_NOT_VALIDATED",
        "NOT_INTERPRETED",
    }

    # FIX:
    # ACTIONABLE_EVIDENCE_GAP previously returned immediately,
    # preventing the already-approved finance retry.
    #
    # Only allow that status through for a tightly scoped,
    # explicitly dated financial request.
    if previous.get("status") not in ordinary_recoverable:
        if not (
            previous.get("status") == "ACTIONABLE_EVIDENCE_GAP"
            and retry_finance
        ):
            return previous

    # Do not guess missing dates or unspecified years.
    if (
        not plan["requested_months"]
        and "documents" not in plan["domains"]
    ):
        return previous

    if retry_finance:
        a, b = sorted(plan["requested_months"])

        from datetime import datetime

        def label(value):
            return datetime.strptime(
                value, "%Y-%m-%d"
            ).strftime("%B %Y")

        # Preserve the existing, historically working finance
        # divergence investigation phrasing when direction is explicit.
        if is_finance_bridge(question, plan):
            bounded = (
                "Why did revenue increase but contribution profit "
                f"decrease from {label(a)} to {label(b)}?"
            )
        else:
            # No direction is assumed for a neutral comparison.
            bounded = (
                "Compare revenue and contribution profit "
                f"from {label(a)} to {label(b)}."
            )

        try:
            result = await finance_investigator(
                bounded,
                reader,
            )

            periods = (
                result.get("periods", {})
                if isinstance(result, dict)
                else {}
            )

            before = (
                periods.get("before")
                if isinstance(periods, dict)
                else None
            )

            after = (
                periods.get("after")
                if isinstance(periods, dict)
                else None
            )

            if (
                isinstance(result, dict)
                and result.get("route") == "investigation"
                and result.get("executable") is True
                and result.get("causal_claim") is False
                and isinstance(before, (list, tuple))
                and isinstance(after, (list, tuple))
                and len(before) == 2
                and len(after) == 2
                and before[0] == a
                and before[1] == _next_month(a)
                and after[0] == b
                and after[1] == _next_month(b)
            ):
                return {
                    **result,
                    "investigation_gateway": {
                        "status": "GOVERNED_FINANCE_RETRY",
                        "original_question": question,
                        "bounded_question": bounded,
                        "previous_route": previous.get("route"),
                        "previous_status": previous.get("status"),
                        "gemini_executed_tools": False,
                        "causal_claim": False,
                    },
                }

        except Exception:
            # The original evidence status remains authoritative.
            pass

        # If this was already an evidence gap, do not replace
        # it with a second speculative evidence plan.
        if previous.get("status") == "ACTIONABLE_EVIDENCE_GAP":
            return previous

    measured = await _approved_monthly_metrics(
        plan,
        reader,
    )

    if measured is not None:
        return measured

    return _safe_gap(question, previous, plan)
