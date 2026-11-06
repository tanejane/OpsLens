"""Deterministic negative and positive coverage for the Phase 5.3F review contract."""
from __future__ import annotations
import copy
from scripts.phase5_3f_pre_ui_review import summarize

def main():
    core={'mode':'live_gemini','status':'EVALUATION_PASSED','score':{'passed':7,'total':7,'observed_responses':7},
          'cases':[{'id':str(i),'passed':True,'failure_codes':[]} for i in range(7)]}
    classes=['MEASURED_DESCRIPTIVE']*3+['ACTIONABLE_EVIDENCE_GAP']*9
    inc={'mode':'live','score':{'incidents_attempted':12,'responses_observed':12,'safety_passed':12,'safety_total':12,'investigations_verified':0},
         'cases':[{'id':f'INC_{i:03d}'} for i in range(1,13)],
         'diagnostic_coverage':{'cases':{f'INC_{i:03d}':{'classification':c} for i,c in enumerate(classes,1)}}}
    gate={'status':'SCOPED_UI_HANDOFF_READY'}
    checks=[]
    def ck(name,passed):checks.append((name,bool(passed)))
    good=summarize(core,inc,gate)
    ck('valid scoped case may hand off',good['ui_design_scope']['implementation_acceptance_approved'])
    ck('mechanisms not implied',good['incidents']['independent_mechanisms_verified']==0)
    ck('plan remains plan',good['incidents']['coverage_counts']['ACTIONABLE_EVIDENCE_GAP']==9)
    ck('no external gate means no approval',not summarize(core,inc)['ui_design_scope']['implementation_acceptance_approved'])
    badgate={'status':'PRE_UI_GATE_NOT_PASSED'}
    ck('failed gate blocks approval',not summarize(core,inc,badgate)['ui_design_scope']['implementation_acceptance_approved'])
    badcore=copy.deepcopy(core);badcore['cases'][2]['passed']=False;badcore['cases'][2]['failure_codes']=['metric']
    badcore['score']['passed']=6;badcore['status']='EVALUATION_FAILED'
    report=summarize(badcore,inc,badgate)
    ck('core 6/7 retained',report['core']['observed_score']['passed']==6)
    ck('failed core case identified',report['core']['failed_cases'][0]['id']=='2')
    ck('core failure blocks approval',not report['ui_design_scope']['implementation_acceptance_approved'])
    missingcore=copy.deepcopy(core);missingcore['cases'].pop()
    ck('missing case not accepted',not summarize(missingcore,inc,gate)['core']['live_case_records_complete'])
    dupcore=copy.deepcopy(core);dupcore['cases'][-1]['id']='0'
    ck('duplicate core case not accepted',not summarize(dupcore,inc,gate)['core']['live_case_records_complete'])
    missinginc=copy.deepcopy(inc);missinginc['cases'].pop()
    ck('missing incident not accepted',not summarize(core,missinginc,gate)['incidents']['live_response_records_complete'])
    dupinc=copy.deepcopy(inc);dupinc['cases'][-1]['id']='INC_001'
    ck('duplicate incident not accepted',not summarize(core,dupinc,gate)['incidents']['live_response_records_complete'])
    unknown=copy.deepcopy(inc);unknown['diagnostic_coverage']['cases']['INC_012']['classification']='OTHER_UNVERIFIED'
    ck('unhandled incident blocks',not summarize(core,unknown,gate)['ui_design_scope']['implementation_acceptance_approved'])
    ck('unhandled ID surfaced',summarize(core,unknown,gate)['incidents']['by_coverage']['OTHER_UNVERIFIED']==['INC_012'])
    noresp=copy.deepcopy(inc);del noresp['diagnostic_coverage']['cases']['INC_012']
    ck('missing diagnostic cannot vanish',summarize(core,noresp,gate)['incidents']['coverage_counts']['NO_RESPONSE']==1)
    low=copy.deepcopy(inc)
    low['diagnostic_coverage']['cases']['INC_003']['classification']='ACTIONABLE_EVIDENCE_GAP'
    ck('insufficient measured count blocks',not summarize(core,low,gate)['ui_design_scope']['implementation_acceptance_approved'])
    unsafe=copy.deepcopy(inc);unsafe['score']['safety_passed']=11
    ck('safety gap blocks approval',not summarize(core,unsafe,gate)['ui_design_scope']['implementation_acceptance_approved'])
    invalidmode=copy.deepcopy(inc);invalidmode['mode']='score'
    ck('replay not called live',not summarize(core,invalidmode,gate)['incidents']['live_response_records_complete'])
    badc=copy.deepcopy(core);badc['mode']='offline'
    ck('offline not called live',not summarize(badc,inc,gate)['core']['live_case_records_complete'])
    for name,ok in checks:print(('PASS' if ok else 'FAIL')+': '+name)
    print(f'Checks passed: {sum(v for _,v in checks)}/{len(checks)}')
    return 0 if all(v for _,v in checks) else 1
if __name__=='__main__':raise SystemExit(main())
