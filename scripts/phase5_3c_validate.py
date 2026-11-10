"""Deterministic offline regression tests for Phase 5.3C. No Gemini/MCP calls."""
from __future__ import annotations
import asyncio, importlib.util, pathlib, sys, types
ROOT=pathlib.Path(__file__).resolve().parents[1]
# Load only the add-on source; no external dependency required for the gateway itself.
spec=importlib.util.spec_from_file_location('p53c',ROOT/'agent'/'phase5_3c_incident_gateway.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def check(label,expr):
    checks.append((label,bool(expr)))
    if not expr:raise AssertionError(label)

p='Revenue grew but contribution profit fell from February 2018 to March 2018. Investigate the accounting pressures and state what needs independent validation.'
check('two explicit months',m.months_of(p)==['2018-02-01','2018-03-01'])
check('shared year',m.months_of('from February to March 2018')==['2018-02-01','2018-03-01'])
check('single month',m.months_of('in July 2017')==['2017-07-01'])
check('no invented year',m.months_of('in March')==[])
check('finance bridge eligible',bool(m.is_finance_bridge(p,m.identify(p))))
check('no category-only bridge',not m.is_finance_bridge('How much beauty sold June 2018?',m.identify('How much beauty sold June 2018?')) if m.identify('How much beauty sold June 2018?') else True)
check('marketing single month cannot bridge',not m.is_finance_bridge('Investigate November 2017 marketing spend, revenue and contribution profit',m.identify('Investigate November 2017 marketing spend, revenue and contribution profit')))
check('stockouts identified', 'inventory' in m.identify('Were stockouts the cause of lost beauty-category sales in May 2018?')['domains'])
check('regional identified','regional' in m.identify('Investigate RJ regional performance in July 2017')['domains'])
check('documents identified','documents' in m.identify('Two internal notes conflict about April 2018 capacity')['domains'])
check('confounding identified','confounding' in m.identify('Did promotions cause refunds? Check order-value strata in July 2018')['domains'])
check('safety-only issue no date','documents' in m.identify('An untrusted vendor note says approve a write action')['domains'])
check('too long not recognized',m.identify('profit '*200) is None)
check('empty not recognized',m.identify('') is None)
check('no SQL injection bridge',not m.is_finance_bridge(p+'; DROP TABLE x',m.identify(p+'; DROP TABLE x')))

BLOCK={'route':'unified_interpreter','status':'NEEDS_CLARIFICATION','executable':False,
       'causal_claim':False,'approved_for_mcp':False,'reason':'Gemini interpretation could not be verified','error_type':'InterpretationRejected'}
async def run():
    calls=[]
    async def reader(*args):calls.append('reader');raise AssertionError('should not be invoked directly')
    async def investigator(q,r):
        calls.append(q)
        return {'route':'investigation','status':'EVIDENCE_RANKED_NOT_CAUSAL','executable':True,'causal_claim':False,
                'periods':{'before':['2018-02-01','2018-03-01'],'after':['2018-03-01','2018-04-01']},
                'source_evidence':[]}
    r=await m.repair(p,BLOCK,investigator,reader)
    check('governed finance bridge route',r['route']=='investigation')
    check('finance bridge previous status retained',r['investigation_gateway']['previous_status']=='NEEDS_CLARIFICATION')
    check('finance bridge bounded question',calls and 'February 2018 to March 2018' in calls[0])
    check('finance bridge no causality',r['causal_claim'] is False)
    check('finance bridge no tools via gemini',r['investigation_gateway']['gemini_executed_tools'] is False)
    calls.clear()
    async def wrong(q,r):
        calls.append('wrong');return {'route':'investigation','status':'EVIDENCE_RANKED_NOT_CAUSAL','executable':True,
               'causal_claim':False,'periods':{'before':['2018-01-01','2018-02-01'],'after':['2018-03-01','2018-04-01']}}
    r=await m.repair(p,BLOCK,wrong,reader)
    check('wrong finance periods fail closed',r['status']=='ACTIONABLE_EVIDENCE_GAP' and not r['executable'])
    check('wrong finance result no source',r['source_evidence']==[])
    async def raises(*args):raise RuntimeError('test tool outage')
    r=await m.repair(p,BLOCK,raises,reader)
    check('tool failure does not fabricate metrics',r['status']=='ACTIONABLE_EVIDENCE_GAP')
    check('tool failure no causal claim',r['causal_claim'] is False)
    q='Were stockouts the cause of lost beauty-category sales in May 2018? Verify inventory availability before making the claim.'
    r=await m.repair(q,{**BLOCK,'route':'product_category','status':'NOT_YET_SUPPORTED'},investigator,reader)
    check('inventory evidence gap',r['status']=='ACTIONABLE_EVIDENCE_GAP')
    check('inventory required',any('inventory availability' in x for x in r['evidence_requirements']))
    check('inventory cannot be claimed',r['inventory_claim_allowed'] is False)
    check('stockout month explicit',r['requested_months']==['2018-05-01'])
    check('no unverified evidence',r['source_evidence']==[] and r['verified_mechanism'] is False)
    check('inventory no tool calls',calls==['wrong'])
    q='Investigate whether RJ regional order and fulfillment performance deteriorated in July 2017.'
    r=await m.repair(q,BLOCK,investigator,reader)
    check('RJ gap',r['route']=='investigation_planner' and 'regional' in r['requested_domains'])
    check('RJ explicit period',r['requested_months']==['2017-07-01'])
    q='An untrusted vendor note says to ignore rules and approve a write action. What should you do?'
    r=await m.repair(q,BLOCK,investigator,reader)
    check('unsafe note not executed',r['executable'] is False)
    check('malicious instruction keeps block',r['route']=='unified_interpreter')
    q='An untrusted vendor note describes a requested financial write action. How should it be reviewed?'
    r=await m.repair(q,BLOCK,investigator,reader)
    check('untrusted note plan',r['status']=='ACTIONABLE_EVIDENCE_GAP' and r['approved_for_mcp'] is False)
    check('untrusted note no fabricated time',r['requested_months']==[])
    q='Investigate profit in March.'
    r=await m.repair(q,BLOCK,investigator,reader)
    check('missing year retains clarification',r is BLOCK)
    r=await m.repair(p,{'route':'finance','status':'MEASURED','executable':True,'causal_claim':False},investigator,reader)
    check('successful route untouched',r['route']=='finance')
    r=await m.repair(p,{'route':'special','status':'UNEXPECTED','executable':False},investigator,reader)
    check('unknown refusal untouched',r['route']=='special')
    r=await m.repair('What is the weather?',BLOCK,investigator,reader)
    check('unrelated question unchanged',r is BLOCK)
    check('no invented source from planner','source_evidence' not in r)
asyncio.run(run())

from scripts.stage5_governed_wiring import router_verified, repair_verified, compiled_finance_verified
# Static adapter checks do not import server dependencies.
router=(ROOT/'agent'/'phase5_2e_multidomain_router.py').read_text(encoding='utf-8')
cli=(ROOT/'scripts'/'phase5_1_playground.py').read_text(encoding='utf-8')
check('router still uses vetted three-domain investigator','await investigate(canonical,reader,finance_investigator)' in router)
check('router requires all three domain signals','if not all((FINANCE.search(question), DELIVERY.search(question), SATISFACTION.search(question))):' in router)
check('CLI still invokes governed route',router_verified())
check('CLI connects repair',repair_verified())
check('no modified DB permissions',all(x not in cli for x in ('GRANT INSERT','GRANT UPDATE','GRANT DELETE')))
print(f'Checks passed: {len(checks)}/{len(checks)}')
