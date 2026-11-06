"""Read-only pre-UI evaluation review. No model, MCP, DB, or fixture execution.

Provides honest diagnostic segmentation of existing live evaluation reports.
It does not change the canonical acceptance gate or certify incident mechanisms.
"""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

EXPECTED_INCIDENTS = {f'INC_{i:03d}' for i in range(1,13)}
COVERAGE_CLASSES=('MEASURED_DESCRIPTIVE','ACTIONABLE_EVIDENCE_GAP','UNINTERPRETED_OR_BLOCKED','OTHER_UNVERIFIED','NO_RESPONSE')

def _read(path):
    raw=Path(path).read_bytes()
    obj=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(obj,dict):raise ValueError('Report must be a JSON object')
    return obj,hashlib.sha256(raw).hexdigest()

def summarize(core, incidents, previous_gate=None):
    if not isinstance(core,dict) or not isinstance(incidents,dict):raise ValueError('Expected two report objects')
    cases=core.get('cases')
    if not isinstance(cases,list):cases=[]
    passed=[x.get('id') for x in cases if isinstance(x,dict) and x.get('passed') is True]
    failed=[{'id':x.get('id'),'failure_codes':x.get('failure_codes',[]),'route':x.get('observed_route'),
             'status':x.get('observed_status')} for x in cases if isinstance(x,dict) and x.get('passed') is not True]
    # No pass rate extrapolation. Missing case records are an evaluation blind spot.
    core_score=core.get('score',{}) if isinstance(core.get('score'),dict) else {}
    core_complete=(core.get('mode')=='live_gemini' and core_score.get('total')==7
                   and core_score.get('observed_responses')==7 and len(cases)==7
                   and len({x.get('id') for x in cases if isinstance(x,dict)})==7)
    incident_cases=incidents.get('cases')
    if not isinstance(incident_cases,list):incident_cases=[]
    seen=[x.get('id') for x in incident_cases if isinstance(x,dict)]
    missing=sorted(EXPECTED_INCIDENTS-set(seen))
    unexpected=sorted(set(seen)-EXPECTED_INCIDENTS,key=str)
    inc_score=incidents.get('score',{}) if isinstance(incidents.get('score'),dict) else {}
    diag=incidents.get('diagnostic_coverage',{})
    d_cases=diag.get('cases',{}) if isinstance(diag,dict) else {}
    if not isinstance(d_cases,dict):d_cases={}
    breakdown={label:[] for label in COVERAGE_CLASSES}
    for incident_id in sorted(EXPECTED_INCIDENTS):
        row=d_cases.get(incident_id)
        category=row.get('classification') if isinstance(row,dict) else None
        breakdown[category if category in breakdown else 'NO_RESPONSE'].append(incident_id)
    # Strictly no readiness certification when any unhandled case or missed core case exists.
    incident_complete=(incidents.get('mode')=='live' and len(incident_cases)==12 and
                       len(set(seen))==12 and not missing and not unexpected and
                       inc_score.get('responses_observed')==12 and inc_score.get('safety_passed')==12)
    core_pass=(core_complete and core.get('status')=='EVALUATION_PASSED' and
               core_score.get('passed')==7 and not failed)
    unresolved=breakdown['UNINTERPRETED_OR_BLOCKED']+breakdown['OTHER_UNVERIFIED']+breakdown['NO_RESPONSE']
    measured=len(breakdown['MEASURED_DESCRIPTIVE'])
    observed_release_ready=bool(core_pass and incident_complete and not unresolved and measured>=3)
    # This conclusion is scope only; the signed-off gate remains sole authoritative approval.
    flags=[]
    if not core_complete:flags.append('CORE_CASE_RECORDS_INCOMPLETE')
    if not core_pass:flags.append('CORE_REGRESSION_UNRESOLVED')
    if not incident_complete:flags.append('INCIDENT_COVERAGE_OR_SAFETY_UNVERIFIED')
    if unresolved:flags.append('INCIDENTS_REQUIRE_CLASSIFICATION_OR_HANDLING')
    if measured<3:flags.append('MEASURED_INCIDENT_COVERAGE_BELOW_THREE')
    if previous_gate and previous_gate.get('status')!='SCOPED_UI_HANDOFF_READY':
        flags.append('AUTHORITATIVE_PRE_UI_GATE_NOT_PASSED')
    if previous_gate is None:flags.append('AUTHORITATIVE_GATE_REPORT_NOT_SUPPLIED')
    result={'contract':'OPSLENS_PHASE5_3F_PRE_UI_REVIEW_V1',
       'review_status':'SCOPED_DEMO_HANDOFF_CANDIDATE' if observed_release_ready and previous_gate and previous_gate.get('status')=='SCOPED_UI_HANDOFF_READY' else 'REVIEW_COMPLETE_WITH_OPEN_GATES',
       'not_a_certification':True,
       'core':{'live_case_records_complete':core_complete,'observed_score':core_score,'passed_case_ids':passed,
               'failed_cases':failed,'unaccounted_case_count':max(0,7-len(cases))},
       'incidents':{'live_response_records_complete':incident_complete,'observed_score':inc_score,
                    'by_coverage':breakdown,'coverage_counts':{k:len(v) for k,v in breakdown.items()},
                    'missing_ids':missing,'unexpected_ids':unexpected,
                    'independent_mechanisms_verified':inc_score.get('investigations_verified')},
       'open_gates':flags,
       'ui_design_scope':{'design_exploration_can_begin':True,'implementation_acceptance_approved':bool(observed_release_ready and previous_gate and previous_gate.get('status')=='SCOPED_UI_HANDOFF_READY'),
          'supported_demonstration':['Governed KPI comparisons with explicit metric definitions and periods',
             'Validated finance investigation and measured delivery/review trends',
             'Evidence sources, eligibility caveats, and uncertainty shown with results',
             'Actionable missing-evidence explanations rather than invented diagnoses'],
          'must_not_present_as_verified':['All twelve incident mechanisms solved',
             'Unreviewed causal explanations or inventory stockout attribution',
             'Automatic financial writes or external approval bypass',
             'Document-conflict and subgroup-confounding engines without separately verified retrieval and tests']},
       'limitations':['Diagnostic scores reflect the provided finite live runs, not population accuracy',
             'Structured output safety is not an independent audit of tool write controls',
             'Actionable evidence gaps are not measured incident solutions',
             'Independent incident certification requires reviewed evidence provenance']}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core-report',type=Path,required=True)
    p.add_argument('--incident-report',type=Path,required=True)
    p.add_argument('--gate-report',type=Path)
    p.add_argument('--output',type=Path,default=Path('reports/phase5_3f_pre_ui_review.json'))
    args=p.parse_args()
    try:
        core,c_hash=_read(args.core_report)
        incident,i_hash=_read(args.incident_report)
        gate,g_hash=_read(args.gate_report) if args.gate_report else (None,None)
        result=summarize(core,incident,gate)
        result['input_sha256']={'core_report':c_hash,'incident_report':i_hash,'gate_report':g_hash}
    except (ValueError,OSError,UnicodeError) as exc:
        print(json.dumps({'status':'REVIEW_INPUT_ERROR','error':str(exc)},indent=2));return 2
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'review_status':result['review_status'],'core_failed_cases':result['core']['failed_cases'],
      'incident_coverage':result['incidents']['coverage_counts'],'open_gates':result['open_gates'],
      'ui_implementation_approved':result['ui_design_scope']['implementation_acceptance_approved'],
      'report_file':str(args.output)},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
