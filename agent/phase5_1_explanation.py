"""Optional Gemini post-evidence explanation selector.

Gemini chooses among evidence-backed explanation templates; it cannot write
prose, metrics, causes, SQL, or tool requests. The caller renders the selected
template with exact values from the validated investigation result.
"""
from __future__ import annotations

import json
import math


EXPLANATION_PROMPT = """You organize an explanation AFTER a governed business investigation completed.
Choose exactly one available explanation type that best matches the user's question.
Return JSON only with exactly: explanation_type (one listed value), evidence_refs (array).
Copy every evidence reference required for that explanation type exactly.
Do not write narrative text, figures, dates, units, assumptions, causes, hypotheses,
recommendations, SQL, or tool requests. If none is relevant, return explanation_type
"none" and an empty evidence_refs array.
"""


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _codes_for(question: str, result: dict):
    candidates: dict[str, list[str]] = {}
    if result.get("executable") is not True or result.get("causal_claim") is not False:
        return candidates

    premise = result.get("premise") or result.get("financial_premise")
    if isinstance(premise, dict) and premise.get("divergence_confirmed") is True:
        if _number(premise.get("revenue_delta")) is not None and _number(premise.get("contribution_profit_delta")) is not None:
            candidates["finance_divergence"] = [
                "premise.divergence_confirmed", "premise.revenue_delta", "premise.contribution_profit_delta"
            ]

    intensity = result.get("order_normalized_evidence")
    if (isinstance(intensity, dict) and intensity.get("status") == "RECONCILED_INTENSITY_COMPARISON"
        and intensity.get("causal_claim") is False and type(intensity.get("before_orders")) is int
        and intensity["before_orders"] > 0 and type(intensity.get("after_orders")) is int and intensity["after_orders"] > 0):
        rows = intensity.get("components")
        if isinstance(rows, list):
            valid_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("component"), str)
                          and row.get("causal_claim") is False and _number(row.get("before_per_order")) is not None
                          and _number(row.get("after_per_order")) is not None and _number(row.get("change_per_order")) is not None
                          and abs((_number(row["after_per_order"]) - _number(row["before_per_order"])) - _number(row["change_per_order"])) <= 0.000001]
            refs = [f"order_normalized_evidence.components.{row['component']}.change_per_order" for row in valid_rows]
            if rows and len(valid_rows) == len(rows):
                candidates["cost_per_order_context"] = ["order_normalized_evidence.status", *refs]

    observations = result.get("observations")
    if isinstance(observations, list):
        refs = [ref for index, row in enumerate(observations)
                if isinstance(row, dict) and row.get("causal_claim") is False
                and isinstance(row.get("metric_id"), str) and _number(row.get("value")) is not None
                for ref in (f"observations.{index}.metric_id", f"observations.{index}.value")]
        if refs:
            candidates["measured_metrics"] = refs

    changes_key = "operational_changes" if isinstance(result.get("operational_changes"), dict) else "metric_changes"
    changes = result.get(changes_key)
    if isinstance(changes, dict):
        refs = [f"{changes_key}.{metric}.{field}"
                for metric, row in changes.items() if isinstance(row, dict)
                and row.get("causal_claim", False) is False
                and all(_number(row.get(field)) is not None for field in ("before", "after", "delta"))
                for field in ("before", "after", "delta")]
        if refs:
            candidates["period_comparison"] = refs

    product = result.get("evidence") if isinstance(result.get("evidence"), dict) else result
    if (isinstance(product, dict) and product.get("status") == "MEASURED_WITH_SCOPE_LIMITS" and product.get("causal_claim") is False
        and isinstance(product.get("metric_id"), str) and "gmv" in product.get("metric_id", "").lower()
        and _number(product.get("value")) is not None and isinstance(product.get("category"), str)
        and isinstance(product.get("period"), list) and isinstance(product.get("source"), str)):
        candidates["product_gmv"] = ["evidence.metric_id", "evidence.value", "evidence.category", "evidence.period", "evidence.source"]

    return candidates


def validate_plan(raw, candidates):
    """Accept only a code and the exact evidence references available for it."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None
    if not isinstance(raw, dict) or set(raw) != {"explanation_type", "evidence_refs"}:
        return None
    code, refs = raw["explanation_type"], raw["evidence_refs"]
    if code == "none" and refs == []:
        return None
    if not isinstance(code, str) or code not in candidates or not isinstance(refs, list):
        return None
    allowed = candidates[code]
    if any(not isinstance(ref, str) for ref in refs):
        return None
    if len(refs) != len(allowed) or len(set(refs)) != len(refs) or set(refs) != set(allowed):
        return None
    return {"status": "VALIDATED", "explanation_type": code, "evidence_refs": allowed}


async def select_explanation(question: str, result: dict, model_call):
    """Ask Gemini to organize only a safe explanation type after evidence retrieval."""
    candidates = _codes_for(question, result)
    if not candidates or model_call is None:
        return None
    envelope = {
        "available_explanations": candidates,
    }
    raw = await model_call(EXPLANATION_PROMPT, json.dumps(envelope, ensure_ascii=False, allow_nan=False))
    return validate_plan(raw, candidates)


# Presentation choices, not new metrics or query permissions. All values stay local.
NARRATIVE_REFS = {
    'facts_first': ['sections.facts'],
    'accounting_first': ['sections.accounting_contributions'],
    **{'hypothesis_'+key: ['hypotheses.'+key] for key in (
        'finance','product_mix','returns_quality','delivery','satisfaction',
        'inventory','regional','documents','confounding')},
}


def _numeric(value):
    from decimal import Decimal, InvalidOperation
    if isinstance(value,bool) or value is None: return False
    try: return Decimal(str(value)).is_finite()
    except (InvalidOperation,ValueError,TypeError): return False


def narrative_sections(result):
    """Project executor-validated evidence locally, retaining exact values and scopes.

    This is not a validator for arbitrary external records. Only the runtime's
    completed governed results enter here; model output never enters this function.
    """
    from copy import deepcopy
    from agent.business_hypotheses import suggestions
    sections=[]
    seen={}
    def add(kind,text,ref,**context):
        key=(kind,text,None if kind=='limitation' else ref)
        if key in seen:
            if ref and ref not in seen[key]['evidence_refs']:seen[key]['evidence_refs'].append(ref)
            return
        section=dict(kind=kind,text=text,evidence_refs=[ref] if ref else [],causal_claim=False,**deepcopy(context))
        seen[key]=section
        sections.append(section)
    def visit(node,path,depth=0):
        if depth>8 or not isinstance(node,dict): return
        for limit in node.get('limitations',[]) if isinstance(node.get('limitations'),list) else []:
            if isinstance(limit,str):add('limitation',limit,path+'/limitations')
        period=node.get('period')
        if (node.get('causal_claim') is False and node.get('status')=='MEASURED_WITH_SCOPE_LIMITS'
                and isinstance(node.get('metric_id'),str) and _numeric(node.get('value'))
                and isinstance(period,list) and len(period)==2 and isinstance(node.get('source'),str)):
            metric=node['metric_id'].replace('_',' ')
            add('fact',f"{metric.capitalize()} was {node['value']} {node.get('unit','')} for [{period[0]}, {period[1]}).",
                path, value=node['value'],unit=node.get('unit'),period=period,source=node['source'],
                population=node.get('population',{'source_population_rows':node['source_population_rows']} if 'source_population_rows' in node else None),
                category=node.get('category'),time_basis=node.get('time_basis'))
        # Only known evidence containers; exclude raw rows, documents and stage duplicates.
        for key in ('evidence','domain_results','hypothesis_evaluation','order_normalized_evidence','before','after'):
            child=node.get(key)
            if isinstance(child,dict):
                visit(child,path+'/'+key,depth+1)
                for name,row in child.items():
                    if isinstance(row,dict): visit(row,path+'/'+key+'/'+name,depth+2)
        for key in ('observations','measurements','supporting_analyses'):
            for i,row in enumerate(node.get(key,[]) if isinstance(node.get(key),list) else []):
                visit(row,path+'/'+key+'/'+str(i),depth+1)
                if key=='measurements' and isinstance(row,dict):
                    for metric,proof in row.items():
                        visit(proof,path+'/'+key+'/'+str(i)+'/'+metric,depth+2)
    if result.get('executable') is True and result.get('causal_claim') is False:
        visit(result,'/payload')
        premise=result.get('premise',result.get('financial_premise',{}))
        if isinstance(premise,dict) and all(_numeric(premise.get(k)) for k in ('revenue_delta','contribution_profit_delta')):
            key='premise' if 'premise' in result else 'financial_premise'
            add('accounting_contribution',
                f"Revenue changed by {premise['revenue_delta']} and contribution profit by {premise['contribution_profit_delta']} in source currency. These are accounting movements, not identified causes.",
                '/payload/'+key,periods=result.get('periods'),values=premise,
                population=result.get('order_normalized_evidence',{}).get('population_basis'),
                scope_reference='/payload/domain_results' if 'domain_results' in result else '/payload/evidence')
        evaluation=result.get('hypothesis_evaluation',{})
        rows=evaluation.get('hypotheses',[]) if isinstance(evaluation,dict) else []
        rows=rows or result.get('accounting_hypotheses',[])
        if isinstance(rows,dict):rows=rows.get('hypotheses',[])
        for i,row in enumerate(rows if isinstance(rows,list) else []):
            if (isinstance(row,dict) and row.get('evidence_type')=='reconciled_accounting_contribution'
                    and row.get('causal_claim') is False and _numeric(row.get('accounting_profit_impact'))):
                root='/payload/hypothesis_evaluation/hypotheses' if evaluation else '/payload/accounting_hypotheses'
                add('accounting_contribution',f"{row['label']} contributed {row['accounting_profit_impact']} to the profit change under the accounting identity; this does not identify the operational cause.",
                    root+'/'+str(i),periods=result.get('periods'),source=row.get('source'),
                    value=row['accounting_profit_impact'],unit='source_currency_unspecified')
        evidence=result.get('evidence',{})
        if result.get('route')=='refund_concentration' and evidence.get('causal_claim') is False:
            pop=evidence.get('population',{})
            if all(_numeric(pop.get(k)) for k in ('refund_amount','refunded_orders','orders')):
                add('fact',f"Recorded refunds total {pop['refund_amount']} across {pop['refunded_orders']} refunded orders in a purchase cohort of {pop['orders']} orders. This is not refund-date cash flow.",
                    '/payload/evidence',population=pop,period=evidence.get('period'),source=evidence.get('source'),unit=evidence.get('refund_amount_unit'))
        # Existing deterministic conclusions remain useful for complex cohort results.
        # Reference rather than paraphrase their numbers or seller identifiers.
        for i,text in enumerate(result.get('conclusions',[]) if isinstance(result.get('conclusions'),list) else []):
            if isinstance(text,str):add('finding',text,'/payload/conclusions/'+str(i))
    else:
        add('limitation',str(result.get('reason') or 'The requested investigation is not fully supported by validated evidence.'),'/payload/status')
        for limit in result.get('limitations',[]):
            if isinstance(limit,str):add('limitation',limit,'/payload/limitations')
    if result.get('executable') is not True:
        # These records are populated only by retain_validated, not by Gemini.
        for i,entry in enumerate(result.get('validated_evidence',[])):
            if not isinstance(entry,dict):continue
            start=len(sections)
            visit(entry.get('result'),'/payload/validated_evidence/'+str(i)+'/result')
            for section in sections[start:]:
                if section['kind']=='fact':
                    section['kind']='retained_fact'
                    section['scope']='completed_step_only_not_complete_investigation'
    # Reconstruct from reviewed templates, never trust arbitrary hypothesis prose.
    for item in result.get('unverified_hypotheses',[]):
        if not isinstance(item,dict):continue
        approved=suggestions([item.get('hypothesis_id')])
        if approved and item==approved[0]:
            h=approved[0]
            add('hypothesis','Unverified possibility: '+h['hypothesis'],None,
                hypothesis_id=h['hypothesis_id'],status=h['status'],basis=h['basis'],
                missing_evidence=h['missing_evidence'],next_check=h['next_check'])
    add('limitation','Accounting contributions and associations do not establish causes. Unverified possibilities require the stated evidence and checks.',None)
    return sections


async def explain_result(question,result,model_call=None,*,timeout_seconds=15):
    """A failed/invalid optional selector cannot replace or destroy any evidence."""
    import asyncio
    import time
    from copy import deepcopy
    from agent.business_hypotheses import suggestions
    from agent.phase5_3c_incident_gateway import identify, DANGEROUS
    if not isinstance(result,dict):return result
    output=deepcopy(result)
    if output.get('route') == 'security_guidance':
        if output.get('status') != 'SECURITY_GUIDANCE' or output.get('executable') is not False:
            return output
        output['explanation'] = {
            'version': 'opslens.explanation.v1',
            'status': 'DETERMINISTIC',
            'fallback_reason': 'SECURITY_POLICY_GUIDANCE',
            'selection': None,
            'sections': [
                {
                    'kind': 'limitation',
                    'text': message,
                    'evidence_refs': [],
                    'causal_claim': False,
                }
                for message in output.get('conclusions', [])
            ],
            'causal_claim': False,
            'generation': 'deterministic_local_security_policy',
            'provider_elapsed_ms': 0,
            'provider_code': None,
            'evidence_authority': 'application_security_contract',
        }
        return output
    try:
        # Policy blocks, ambiguity and explicit causal refusals are not invitations to speculate.
        eligible=(result.get('causal_claim') is False and
                  (result.get('executable') is True or result.get('status') in
                   ('ACTIONABLE_EVIDENCE_GAP','PARTIAL_GOVERNED_EVIDENCE','MEASURED_WITH_LIMITATIONS')))
        if eligible and isinstance(question,str) and not DANGEROUS.search(question):
            plan=identify(question)
            if plan and 'unverified_hypotheses' not in output:
                output['unverified_hypotheses']=suggestions(plan['domains'])
        sections=narrative_sections(output)
        candidates={}
        if eligible:
            if any(s['kind'] in ('fact','finding') for s in sections):candidates['facts_first']=NARRATIVE_REFS['facts_first']
            if any(s['kind']=='accounting_contribution' for s in sections):candidates['accounting_first']=NARRATIVE_REFS['accounting_first']
            for section in sections:
                if section['kind']=='hypothesis':
                    code='hypothesis_'+section['hypothesis_id'];candidates[code]=NARRATIVE_REFS[code]
        status='DETERMINISTIC';reason='MODEL_DISABLED' if model_call is None else 'NO_ELIGIBLE_SELECTION'
        selection=None
        elapsed_ms=0;provider_code=None
        if model_call is not None and candidates:
            started=time.monotonic()
            try:
                # Explicit outbound allowlist: static codes/references only. No question,
                # figures, periods, populations, identifiers, nested evidence or documents.
                raw=await asyncio.wait_for(model_call(EXPLANATION_PROMPT,json.dumps({'available_explanations':candidates})),timeout_seconds)
                selection=validate_plan(raw,candidates)
                status='MODEL_SELECTED' if selection else 'DETERMINISTIC_FALLBACK'
                reason=None if selection else 'INVALID_OR_EMPTY_SELECTION'
            except Exception as exc:
                status='DETERMINISTIC_FALLBACK';reason='PROVIDER_UNAVAILABLE'
                error_type=type(exc).__name__
                code=getattr(exc,'code',None)
                provider_code=code if type(code) is int else None
            finally:
                elapsed_ms=round((time.monotonic()-started)*1000)
        if selection:
            code=selection['explanation_type']
            def first(s):
                group={'fact':0,'retained_fact':0,'finding':0,'accounting_contribution':0,'hypothesis':1,'limitation':2}[s['kind']]
                preferred=((code=='facts_first' and s['kind'] in ('fact','finding')) or
                    (code=='accounting_first' and s['kind']=='accounting_contribution') or
                    (s.get('hypothesis_id') and code=='hypothesis_'+s['hypothesis_id']))
                return group,not preferred
            sections.sort(key=first)  # Facts always precede speculation; nothing is omitted.
        else:
            sections.sort(key=lambda s: {'fact':0,'retained_fact':0,'finding':0,'accounting_contribution':0,'hypothesis':1,'limitation':2}[s['kind']])
        output['explanation']={'version':'opslens.explanation.v1','status':status,'fallback_reason':reason,
            'selection':selection,'sections':sections,'causal_claim':False,
            'generation':'reviewed_templates_with_exact_local_evidence',
            'provider_elapsed_ms':elapsed_ms,'provider_code':provider_code,
            'evidence_authority':'original_payload_and_validators'}
        if 'error_type' in locals():output['explanation']['error_type']=error_type
    except Exception as exc:
        # Local rendering bugs also cannot convert a valid investigation into HTTP 503.
        output=deepcopy(result)
        output['explanation']={'version':'opslens.explanation.v1','status':'DETERMINISTIC_FALLBACK',
            'fallback_reason':'RENDERING_UNAVAILABLE','error_type':type(exc).__name__,
            'sections':[],'causal_claim':False,'evidence_authority':'original_payload_and_validators'}
    return output
