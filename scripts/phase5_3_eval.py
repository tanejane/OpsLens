"""Phase 5.3A: reproducible, fail-closed OpsLens evaluation; no new authority.

Run offline for contract tests. `live` invokes the EXISTING unified CLI as a child
process, evaluates observable output only, and never asserts unseen tool actions.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Case:
    id: str
    query: str
    routes: tuple[str,...]
    statuses: tuple[str,...]
    executable: bool
    metric: str|None=None
    expected_value: str|None=None
    period: tuple[str,str]|None=None
    cohort: bool=False

# Supported scope, not a claim to cover arbitrary user questions.
CASES=(
 Case('product_typo','eh how much beuty item GMV in Jun 2018 ah?',('product_category',),('MEASURED_WITH_SCOPE_LIMITS',),True,'item_gmv','107908.82',('2018-06-01','2018-07-01')),
 Case('delivery_typo','what was the late delivry rate in june 2018?',('delivery_operations',),('MEASURED_WITH_SCOPE_LIMITS',),True,'late_delivery_rate','1.3943569553805774',('2018-06-01','2018-07-01')),
 Case('sales_clarify','How were sales in June 2018?',('language_clarification',),('NEEDS_CLARIFICATION',),False),
 Case('multidomain','Compare finance, late delivery and review scores from February 2018 to March 2018',('three_domain_investigation',),('THREE_DOMAIN_DESCRIPTIVE_EVIDENCE',),True,period=('2018-02-01','2018-03-01'),cohort=True),
 Case('shared_year','Revenue increased but profit fell between February and March 2018. Did delivery and customer satisfaction also get worse?',('three_domain_investigation',),('THREE_DOMAIN_DESCRIPTIVE_EVIDENCE',),True,period=('2018-02-01','2018-03-01'),cohort=True),
 Case('causal_refusal','Did delivery delays cause poor reviews and profit decline between February and March 2018?',('three_domain_investigation',),('NEEDS_CLARIFICATION',),False),
 Case('delivery_after_multidomain','What was the late delivery rate in June 2018?',('delivery_operations',),('MEASURED_WITH_SCOPE_LIMITS',),True,'late_delivery_rate','1.3943569553805774',('2018-06-01','2018-07-01')),
)

class EvaluationError(ValueError): pass

def _number(value):
    if value is None or isinstance(value,bool):raise EvaluationError('INVALID_NUMERIC_VALUE')
    try: d=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as e:raise EvaluationError('INVALID_NUMERIC_VALUE') from e
    if not d.is_finite():raise EvaluationError('NONFINITE_NUMERIC_VALUE')
    return d

def evaluate_case(case:Case,response:dict,*,audit_attached=False):
    """Return independent assertion results, not model self-reported confidence."""
    checks={}
    if not isinstance(response,dict):return {'passed':False,'checks':{'response_object':False},'failure_codes':['INVALID_RESPONSE']}
    checks['route']=response.get('route') in case.routes
    checks['status']=response.get('status') in case.statuses
    checks['executable']=response.get('executable') is case.executable
    checks['causal_claim']=response.get('causal_claim') is False
    if case.executable:
        if case.id in ('multidomain','shared_year'):
            checks['not_mcp_approved']=response.get('approved_for_mcp') is False
            checks['finance_population_distinct']=response.get('evidence_relation')=='PERIOD_ALIGNED_SEPARATE_FINANCIAL_AND_OPERATIONAL_POPULATIONS'
            p=response.get('periods') or {}
            checks['period']=isinstance(p,dict) and p.get('before')==['2018-02-01','2018-03-01'] and p.get('after')==['2018-03-01','2018-04-01']
            checks['domains']=response.get('domains')==['finance','delivery_operations','customer_satisfaction']
            changes=response.get('operational_changes') or {}
            checks['measured_three_operational_metrics']=isinstance(changes,dict) and set(changes)=={'late_delivery_rate','average_review_score','low_rating_rate'}
            checks['financial_direction']=False
            try:
                f=response['financial_premise']
                checks['financial_direction']=f.get('divergence_confirmed') is True and _number(f['revenue_delta'])>0 and _number(f['contribution_profit_delta'])<0
                checks['approx_revenue']=abs(_number(f['revenue_delta'])-Decimal('139034.73'))<=Decimal('0.02')
                checks['approx_profit']=abs(_number(f['contribution_profit_delta'])+Decimal('48578.128924'))<=Decimal('0.02')
            except (KeyError,TypeError,EvaluationError):
                checks['approx_revenue']=False;checks['approx_profit']=False
            checks['cohort_trace_scope']=True
            if audit_attached and case.cohort:
                c=response.get('operational_cohort_evidence') or {}
                checks['cohort_trace_scope']=c.get('status')=='EXACT_ORDER_COHORT_RECONCILED' and c.get('scope')=='delivery_and_review_base_views_only' and c.get('exact_order_id_sets_verified') is True and c.get('approved_for_mcp') is False
        else:
            e=response.get('evidence') or {}
            checks['metric']=e.get('metric_id')==case.metric
            checks['period']=e.get('period')==list(case.period)
            try:checks['value']=abs(_number(e.get('value'))-_number(case.expected_value))<=Decimal('0.000001')
            except EvaluationError:checks['value']=False
            if case.id=='product_typo':
                checks['category']=e.get('category')=='beleza_saude'
                checks['inventory_refused']=response.get('inventory_claim_allowed') is False
    else:
        checks['no_mcp_authority']=response.get('approved_for_mcp') is not True
        checks['no_metric_evidence']=not response.get('evidence')
    fails=[k for k,v in checks.items() if v is not True]
    return {'passed':not fails,'checks':checks,'failure_codes':fails}

def extract_json_results(stdout:str):
    """Extract pretty JSON responses from the CLI; ignore SDK log lines."""
    segments=re.split(r'OpsLens >\s*',stdout)[1:]
    parsed=[]
    decoder=json.JSONDecoder()
    for seg in segments:
        match=re.search(r'(?m)^\{',seg)
        if match:
            try: parsed.append(decoder.raw_decode(seg[match.start():])[0])
            except json.JSONDecodeError:parsed.append({'_parse_error':'INVALID_JSON'})
        elif seg.strip().startswith('exit') or not seg.strip():
            continue
        else:parsed.append({'_parse_error':'MISSING_JSON','excerpt':seg[:150]})
    return parsed

def incident_manifest(root:Path):
    files=list(sorted((root/'data'/'eval_ground_truth').glob('incident_*.json')))
    expected=[f'incident_{i:03d}.json' for i in range(1,13)]
    found={f.name:f for f in files}
    # Inventory only: the live conversational case suite is NOT the incident eval.
    return {'expected':12,'present':sum(x in found for x in expected),
            'missing':[x for x in expected if x not in found],
            'execution_status':'NOT_EXECUTED','warning':'Ground-truth files alone are not proof of incident-level evaluation'}

def summarize(cases,observed,elapsed,mode,audit):
    results=[]
    for i,c in enumerate(cases):
        if i<len(observed):r=evaluate_case(c,observed[i],audit_attached=audit)
        else:r={'passed':False,'checks':{'response_present':False},'failure_codes':['MISSING_RESPONSE']}
        results.append({'id':c.id,'input':c.query,'passed':r['passed'],'checks':r['checks'],'failure_codes':r['failure_codes'],
                        'observed_route':observed[i].get('route') if i<len(observed) and isinstance(observed[i],dict) else None,
                        'observed_status':observed[i].get('status') if i<len(observed) and isinstance(observed[i],dict) else None})
    passed=sum(x['passed'] for x in results)
    return {'contract':'OPSLENS_PHASE5_3_EVAL_V1','mode':mode,'status':'EVALUATION_PASSED' if passed==len(cases) and len(observed)==len(cases) else 'EVALUATION_FAILED',
            'score':{'passed':passed,'total':len(cases),'pass_rate':round(passed/len(cases),4), 'observed_responses':len(observed)},
            'total_wall_seconds':round(elapsed,3),'cohort_audit_attached':audit,'limitations':['This is a narrow, fixed regression suite, not a claim to understand every user question',
              'Case pass rates are not independent estimates of population accuracy','CLI stdout does not establish per-tool authorization by itself',
              'Latency is whole-run wall time, not per-call latency or token billing'],
            'incident_evaluation':incident_manifest(ROOT),'cases':results}

def run_offline():
    from agent.phase5_2e_multidomain_router import decision
    # Offline routing assertions with the *installed* router: no Gemini, MCP or DB.
    checks=[]
    for q,expected in [
      ('Compare finance, late delivery and review scores from February 2018 to March 2018','execute'),
      ('Revenue increased but profit fell between February and March 2018. Did delivery and customer satisfaction also get worse?','execute'),
      ('Did delivery delays cause poor reviews and profit decline between February and March 2018?','reject'),
      ('Compare finance delivery reviews between February and March','reject'),
      ('Compare finance delivery reviews from March 2018 to February 2018','reject'),
      ('Compare finance delivery reviews from February 2018 to March 2018; DROP TABLE x','reject'),
      ('What was the late delivery rate in June 2018?',None),
      ('What was beauty item GMV in June 2018?',None),
    ]:
        d=decision(q);actual=d[0] if d else None
        checks.append({'name':'routing: '+q,'passed':actual==expected})
    # Independent evaluator: test good and tampered outputs, not just parser smoke.
    product={'route':'product_category','status':'MEASURED_WITH_SCOPE_LIMITS','executable':True,'causal_claim':False,'inventory_claim_allowed':False,
             'evidence':{'metric_id':'item_gmv','category':'beleza_saude','value':'107908.82','period':['2018-06-01','2018-07-01']}}
    target=CASES[0]
    checks.append({'name':'valid measurement accepted','passed':evaluate_case(target,product)['passed']})
    for key,evil in [('value','999999'),('metric_id','effective_revenue'),('category','shoes'),('period',['2018-07-01','2018-08-01'])]:
        r=json.loads(json.dumps(product));r['evidence'][key]=evil
        checks.append({'name':'tampered '+key+' rejected','passed':not evaluate_case(target,r)['passed']})
    for key,evil in [('causal_claim',True),('executable',False),('status','UNVERIFIED'),('route','delivery_operations')]:
        r=json.loads(json.dumps(product));r[key]=evil
        checks.append({'name':'tampered '+key+' rejected','passed':not evaluate_case(target,r)['passed']})
    blocked={'route':'three_domain_investigation','status':'NEEDS_CLARIFICATION','executable':False,
             'causal_claim':False,'approved_for_mcp':False,'reason':'Causal attribution is not supported'}
    checks.append({'name':'causal refusal accepted','passed':evaluate_case(CASES[5],blocked)['passed']})
    blocked['executable']=True
    checks.append({'name':'causal answer not executable','passed':not evaluate_case(CASES[5],blocked)['passed']})
    demo='OpsLens > a?\n[INFO] model\n{\n  "route": "a",\n  "status": "b"\n}\n\nOpsLens > exit\n'
    checks.append({'name':'CLI JSON parser skips SDK log','passed':extract_json_results(demo)==[{'route':'a','status':'b'}]})
    checks.append({'name':'CLI JSON parser rejects invalid','passed':extract_json_results('OpsLens > x\n{bad json}\n')[0].get('_parse_error')=='INVALID_JSON'})
    checks.append({'name':'incident fixtures never counted as executed','passed':incident_manifest(ROOT)['execution_status']=='NOT_EXECUTED'})
    checks.append({'name':'case suite nonempty and unique','passed':len(set(c.id for c in CASES))==len(CASES) and len(CASES)>5})
    return checks

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['offline','live'])
    p.add_argument('--gemini',action='store_true',help='Live only; calls the existing Gemini model')
    p.add_argument('--cohort-audit',type=Path,help='Live only; optional validated Phase 5.2D raw audit artifact')
    p.add_argument('--output',type=Path,default=Path('reports/phase5_3_evaluation.json'))
    p.add_argument('--timeout',type=int,default=240)
    args=p.parse_args()
    started=time.monotonic()
    if args.mode=='offline':
        checks=run_offline();ok=all(x['passed'] for x in checks)
        report={'contract':'OPSLENS_PHASE5_3_EVAL_V1','mode':'offline','status':'OFFLINE_CONTRACTS_PASSED' if ok else 'OFFLINE_CONTRACTS_FAILED',
                'score':{'passed':sum(x['passed'] for x in checks),'total':len(checks)},'checks':checks,
                'incident_evaluation':incident_manifest(ROOT),
                'warning':'No live MCP/Gemini requests or incident investigator scoring occurred'}
    else:
        if args.timeout<30: p.error('--timeout must be >= 30')
        cmd=[sys.executable,'-m','scripts.phase5_1_playground']
        if args.gemini:cmd.append('--gemini')
        if args.cohort_audit:
            if not args.cohort_audit.is_file():p.error('Audit artifact not found')
            cmd+=['--cohort-audit',str(args.cohort_audit.resolve())]
        queries='\n'.join(c.query for c in CASES)+'\nexit\n'
        try:
            run=subprocess.run(cmd,input=queries,text=True,capture_output=True,cwd=ROOT,timeout=args.timeout,encoding='utf-8',errors='replace')
            observed=extract_json_results(run.stdout)
            report=summarize(CASES,observed,time.monotonic()-started,'live_gemini' if args.gemini else 'live_deterministic',bool(args.cohort_audit))
            report['child_exit_code']=run.returncode
            report['stdout_sha256']=hashlib.sha256(run.stdout.encode()).hexdigest()
            report['stderr_sha256']=hashlib.sha256(run.stderr.encode()).hexdigest()
            report['case_source']='fixed_v1'
            if run.returncode or run.stderr and ('Traceback ' in run.stderr):
                report['status']='EVALUATION_FAILED'
                report['execution_error']='Child application exited nonzero or emitted traceback'
        except subprocess.TimeoutExpired:
            report={'contract':'OPSLENS_PHASE5_3_EVAL_V1','mode':'live','status':'EVALUATION_FAILED',
                    'execution_error':'TIMEOUT','timeout_seconds':args.timeout,'incident_evaluation':incident_manifest(ROOT)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'mode':report['mode'],'score':report.get('score'),
        'incident_evaluation':report['incident_evaluation'],'report_file':str(args.output)},indent=2))
    return 0 if report['status'] in ('OFFLINE_CONTRACTS_PASSED','EVALUATION_PASSED') else 1

if __name__=='__main__':raise SystemExit(main())
