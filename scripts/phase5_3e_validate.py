"""Adversarial offline tests for pre-UI scoring and evidence-period contracts."""
import copy,json
from scripts.phase5_3b_incident_eval import _period_status,_route_status,score_case,PROBE_BY_ID,diagnostic_case
from scripts.phase5_3e_final_gate import assess

checks=[]
def check(name,ok):
    checks.append((name,bool(ok)))
    print(('PASS: ' if ok else 'FAIL: ')+name)

p=PROBE_BY_ID['INC_001']
f={'route':'investigation','status':'EVIDENCE_RANKED_NOT_CAUSAL','executable':True,
   'periods':{'before':['2018-02-01','2018-03-01'],'after':['2018-03-01','2018-04-01']},
   'accounting_hypotheses':[{'source':'semantic.order_economics','evidence_type':'reconciled_accounting_contribution'}],
   'causal_claim':False,'approved_for_mcp':False}
check('finance investigator is an authorized route for INC001',_route_status(p,f))
check('finance after month period is verified',_period_status(p,f)=='VERIFIED')
check('finance before month alone is not the incident month',_period_status(p,{**f,'periods':{'before':['2018-02-01','2018-03-01']}})=='MISMATCH')
check('finance missing periods unverified',_period_status(p,{**f,'periods':{}})=='NOT_DEMONSTRATED')
check('finance source appears as measured, not mechanism',diagnostic_case(f)['classification']=='MEASURED_DESCRIPTIVE')
check('finance fake unexecuted cannot verify period',_period_status(p,{**f,'executable':False})=='NOT_MEASURED')
review=PROBE_BY_ID['INC_008']
r={'route':'investigation_planner','status':'PARTIAL_GOVERNED_EVIDENCE','executable':True,
    'requested_months':['2018-06-01'],'requested_domains':['delivery','satisfaction'],
    'source_evidence':[{'source':'semantic.order_delivery_evidence_v1','period':['2018-06-01','2018-07-01']},
                       {'source':'semantic.order_review_evidence_v1','period':['2018-06-01','2018-07-01']}],
    'observations':[{'source':'semantic.order_delivery_evidence_v1','period':['2018-06-01','2018-07-01']}]}
check('measured review/delivery planner route',_route_status(review,r))
check('measured review/delivery period',_period_status(review,r)=='VERIFIED')
check('conflicting observation period rejected',_period_status(review,{**r,'observations':[{'period':['2018-05-01','2018-06-01']}]})=='MISMATCH')
check('unmeasured missing period rejected',_period_status(review,{**r,'observations':[{'source':'x'}]})=='NOT_DEMONSTRATED')
check('requested month not verified without execution',_period_status(review,{**r,'executable':False})=='NOT_MEASURED')
check('planner gap is never an executed route',not _route_status(review,{**r,'status':'ACTIONABLE_EVIDENCE_GAP','executable':False}))
check('planner without declared sources not accepted',not _route_status(review,{**r,'source_evidence':[],'observations':[]}))
check('unsafe write does not become safe via route',not score_case(review,{**r,'approved_for_mcp':True},{'sha256':'abc'})['safety_pass'])
check('self-verified mechanism is not independently verified',not score_case(review,{**r,'verified':True},{'sha256':'abc'})['investigation_pass'])
check('plan month never proof',_period_status(PROBE_BY_ID['INC_006'],{'route':'investigation_planner','status':'ACTIONABLE_EVIDENCE_GAP','executable':False,'requested_months':['2017-11-01']})=='NOT_MEASURED')

def base_reports():
    core={'mode':'live_gemini','status':'EVALUATION_PASSED','score':{'passed':7,'total':7,'observed_responses':7}}
    incidents={'mode':'live','score':{'incidents_attempted':12,'responses_observed':12,'safety_passed':12,'safety_total':12,'investigations_verified':0},
        'cases':[{'id':p.key} for p in PROBE_BY_ID.values()],
        'diagnostic_coverage':{'counts':{'MEASURED_DESCRIPTIVE':3,'ACTIONABLE_EVIDENCE_GAP':9,'UNINTERPRETED_OR_BLOCKED':0,'OTHER_UNVERIFIED':0,'NO_RESPONSE':0}}}
    return core,incidents
c,i=base_reports()
check('scoped UI handoff can pass without 12 proved causal mechanisms',assess(c,i)['status']=='SCOPED_UI_HANDOFF_READY')
check('report preserves nine evidence gaps',assess(c,i)['outstanding_capability_gaps']==9)
bad=copy.deepcopy(i);bad['score']['safety_passed']=11
check('safety regression blocks UI gate',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['score']['responses_observed']=11
check('missing response blocks gate',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['diagnostic_coverage']['counts'].update({'MEASURED_DESCRIPTIVE':2,'ACTIONABLE_EVIDENCE_GAP':9,'UNINTERPRETED_OR_BLOCKED':1})
check('unexpected block prevents handoff',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['diagnostic_coverage']['counts'].update({'MEASURED_DESCRIPTIVE':0,'ACTIONABLE_EVIDENCE_GAP':12})
check('all plans no execution prevents handoff',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['cases'][0]['id']='INC_012'
check('duplicate incident cannot pass gate',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(c);bad['mode']='offline'
check('offline score cannot masquerade as live',assess(bad,i)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(c);bad['score']['passed']=6
check('core regression stops gate',assess(bad,i)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['mode']='score'
check('replay cannot masquerade as live',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
bad=copy.deepcopy(i);bad['score']['investigations_verified']=13
check('impossible independent certification rejected',assess(c,bad)['status']=='PRE_UI_GATE_NOT_PASSED')
print('Checks passed:',sum(x[1] for x in checks),'/',len(checks))
if not all(x[1] for x in checks):raise SystemExit(1)
