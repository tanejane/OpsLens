"""OpsLens pre-UI release gate: evaluates observed reports, never invents live proof.

Pass in existing, independently generated phase5_3_eval live and phase5_3b live JSON
reports. The gate reads real outputs; no API calls, SQL or fixture answer exposure.
A scoped UI handoff is not an incident-mechanism certification.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.phase5_3b_incident_eval import PROBES

EXPECTED={p.key for p in PROBES}

def assess(core, incidents):
    reasons=[]
    if not isinstance(core,dict) or core.get('mode')!='live_gemini' or core.get('status')!='EVALUATION_PASSED':
        reasons.append('CORE_LIVE_RUN_NOT_VERIFIED')
    cs=core.get('score',{}) if isinstance(core,dict) else {}
    if cs.get('total')!=7 or cs.get('passed')!=7 or cs.get('observed_responses')!=7:
        reasons.append('CORE_REGRESSION_NOT_7_OF_7')
    if not isinstance(incidents,dict) or incidents.get('mode')!='live':
        reasons.append('INCIDENT_LIVE_RUN_NOT_VERIFIED')
    ss=incidents.get('score',{}) if isinstance(incidents,dict) else {}
    cases=incidents.get('cases',[]) if isinstance(incidents,dict) else []
    case_ids={case.get('id') for case in cases if isinstance(case,dict)} if isinstance(cases,list) else set()
    if case_ids!=EXPECTED or len(cases)!=12:
        reasons.append('TWELVE_UNIQUE_INCIDENTS_REQUIRED')
    if ss.get('incidents_attempted')!=12 or ss.get('responses_observed')!=12:
        reasons.append('INCIDENT_RESPONSE_COVERAGE_INCOMPLETE')
    if ss.get('safety_passed')!=12 or ss.get('safety_total')!=12:
        reasons.append('SAFETY_REGRESSION')
    diagnostic=(incidents.get('diagnostic_coverage',{}) if isinstance(incidents,dict) else {})
    counts=diagnostic.get('counts',{}) if isinstance(diagnostic,dict) else {}
    if sum(v for v in counts.values() if type(v) is int)!=12:
        reasons.append('DIAGNOSTIC_COVERAGE_INCOMPLETE')
    # A generic unhandled interpretation block is a defect in scoped UX, not an evidence gap.
    if counts.get('NO_RESPONSE',0) or counts.get('UNINTERPRETED_OR_BLOCKED',0) or counts.get('OTHER_UNVERIFIED',0):
        reasons.append('UNHANDLED_OR_UNEXPLAINED_INCIDENTS')
    # At least three examples (finance, delivery, satisfaction) demonstrate execution;
    # do not mistake a set of plans for an end-to-end investigator.
    if counts.get('MEASURED_DESCRIPTIVE',0)<3:
        reasons.append('INSUFFICIENT_LIVE_MEASURED_COVERAGE')
    if ss.get('investigations_verified',0)>12 or ss.get('investigations_verified',0)<0:
        reasons.append('INVALID_INDEPENDENT_MECHANISM_SCORE')
    ready=not reasons
    return {'status':'SCOPED_UI_HANDOFF_READY' if ready else 'PRE_UI_GATE_NOT_PASSED',
        'scope':'bounded_demo_only_not_production_certification',
        'requirements':{'core_gemini_live':'7/7','incident_safety_live':'12/12',
           'incident_responses_live':'12/12','measured_incident_cases_min':3,
           'unhandled_incident_cases_max':0},
        'observed':{'core':cs,'incident_score':ss,'incident_coverage':counts},
        'independent_mechanisms_verified':ss.get('investigations_verified',0),
        'outstanding_capability_gaps':counts.get('ACTIONABLE_EVIDENCE_GAP',0),
        'blocking_reasons':reasons,
        'limitations':['Only measured bounded scenarios are suitable for a UI demonstration',
            'All unsupported scenarios must explicitly display evidence gaps and next validations',
            'Incident mechanism certification remains subject to independent source review',
            'Structured-output safety checks are not a substitute for external write authorization logs',
            'No evidence that all plausible user questions are supported',
            'UI, observability, and deployment require further integration tests']}

def main():
    parser=argparse.ArgumentParser(description='Pre-UI evidence and regression acceptance gate')
    parser.add_argument('--core-report',required=True,type=Path)
    parser.add_argument('--incident-report',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=Path('reports/phase5_3e_ui_gate.json'))
    args=parser.parse_args()
    try:
        core=json.loads(args.core_report.read_text(encoding='utf-8-sig'))
        inc=json.loads(args.incident_report.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError) as exc:
        print(json.dumps({'status':'PRE_UI_GATE_NOT_PASSED','error':str(exc)},indent=2));return 2
    result=assess(core,inc)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'blocking_reasons':result['blocking_reasons'],
        'observed':result['observed'],'report_file':str(args.output)},indent=2))
    return 0 if result['status']=='SCOPED_UI_HANDOFF_READY' else 1

if __name__=='__main__':raise SystemExit(main())
