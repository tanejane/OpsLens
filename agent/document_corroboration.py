"""Document passages are untrusted data, never instructions or causal proof."""
from copy import deepcopy
from datetime import date
from decimal import Decimal,InvalidOperation
import hashlib,json,re
from agent.investigation_state import BudgetStop

REQUEST=re.compile(r'\b(documents?|documentation|notes?|memos?|corroborat\w*|cross.check|business reports?)\b',re.I)
INJECTION=re.compile(r'ignore\s+(?:all\s+|the\s+)?(?:previous|instructions)|system\s*prompt|developer\s*message|bypass|auto.approve|execute\s+(?:sql|code)|run_readonly_sql|reveal\s+.*(?:key|secret)|\b(?:drop|grant|delete)\s+(?:table|select|from)',re.I)

def measurements(payload):
    found=[]
    def visit(value,path):
        if isinstance(value,dict):
            if all(k in value for k in ('metric_id','value','period','source','unit')) and isinstance(value['period'],list) and len(value['period'])==2:
                try:
                    number=Decimal(str(value['value']))
                    if number.is_finite():found.append({'path':path,**{k:deepcopy(value.get(k)) for k in ('metric_id','value','period','source','unit','population')}})
                except (InvalidOperation,ValueError):pass
            for k,v in value.items():
                if k not in ('document_evidence','database_record','execution_trace'):visit(v,path+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):visit(v,path+'/'+str(i))
    visit(payload,'/payload')
    return found

def assess(hits,payload,question,*,today=None):
    from retrieval.hybrid import _injection_flag
    from agent.retrieval_phase3c import _looks_like_prompt_injection
    if not isinstance(hits,list) or len(hits)>5:raise ValueError('Invalid bounded retrieval response')
    today=today or date.today(); db=measurements(payload); entries=[];seen=set()
    terms=set(re.findall(r'[a-z]{4,}',question.lower()))-{'documents','document','notes','reports','what','with','this','that','corroborate','check','evidence'}
    for hit in hits:
        if not isinstance(hit,dict):raise ValueError('Malformed retrieved hit')
        text=hit.get('content','')
        if not isinstance(text,str) or len(text)>16000:raise ValueError('Passage exceeds bounded context')
        identity=(hit.get('document_id'),hit.get('chunk_id'))
        if identity in seen:continue
        seen.add(identity)
        entry={'source':deepcopy(hit),'content_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'version':None,'version_status':'UNVERIFIED_NOT_IN_INDEX','date_status':'UNVERIFIED_INFERRED_INDEX_DATE',
            'disposition':'CONTEXT_ONLY','comparisons':[],'causal_claim':False}
        version=re.search(r'^Version:\s*(\S+)',text,re.M|re.I)
        if version:entry['version']=version.group(1);entry['version_status']='DOCUMENT_DECLARED_NOT_REGISTRY_VERIFIED'
        try:issued=date.fromisoformat(str(hit.get('source_date'))[:10])
        except ValueError:issued=None
        if not all(isinstance(hit.get(k),str) and 0<len(hit[k])<=512 for k in ('document_id','chunk_id','filename','source_type')):entry['disposition']='MISSING_PROVENANCE'
        elif hit.get('injection_flag') or hit.get('blocked_from_context') or _injection_flag(text) or INJECTION.search(text) or _looks_like_prompt_injection(text):entry['disposition']='REJECTED_INJECTION'
        elif hit.get('trust_level')!='internal':entry['disposition']='REJECTED_TRUST'
        elif issued is None:entry['disposition']='MISSING_DATE'
        elif issued>today:entry['disposition']='FUTURE_DATED'
        elif re.search(r'^(?:Status:|#)[^\n]*\b(preliminary|early draft|superseded|obsolete|incomplete)\b',text,re.I|re.M):entry['disposition']='OUTDATED_OR_PROVISIONAL'
        elif not terms.intersection(re.findall(r'[a-z]{4,}',text.lower())):entry['disposition']='IRRELEVANT'
        else:
            # Explicit claim records embedded in business text. Never extract an
            # unlabeled number or equate incompatible metric populations.
            for match in re.finditer(r'^Measurement:\s*(\{[^\n]+\})\s*$',text,re.M):
                comparison={'passage':match.group(0),'disposition':'UNVERIFIABLE_CLAIM'}
                try:
                    claim=json.loads(match.group(1));value=Decimal(str(claim['value']))
                    if not value.is_finite():raise ValueError('Nonfinite claim')
                    required=('metric_id','period','source','unit','population')
                    candidates=[m for m in db if isinstance(m['population'],dict) and m['population'] and all(k in claim and claim[k]==m[k] for k in required)]
                    if candidates:
                        if issued<date.fromisoformat(claim['period'][1]):
                            comparison['disposition']='PRE_PERIOD_CLOSE_CLAIM'
                            entry['comparisons'].append(comparison)
                            continue
                        outcomes={Decimal(str(m['value']))==value for m in candidates}
                        comparison.update(claim=claim,database_references=[m['path'] for m in candidates],
                            disposition='DATABASE_AMBIGUITY' if len(outcomes)>1 else 'CORROBORATES' if True in outcomes else 'CONTRADICTS',
                            database_values=[m['value'] for m in candidates])
                except (ValueError,KeyError,TypeError,InvalidOperation):pass
                entry['comparisons'].append(comparison)
            if entry['comparisons']:
                outcomes={c['disposition'] for c in entry['comparisons']}
                entry['disposition']='CONTRADICTS' if 'CONTRADICTS' in outcomes else 'CORROBORATES' if outcomes=={'CORROBORATES'} else 'NOT_FULLY_VERIFIABLE'
        entries.append(entry)
    # Only compare explicitly declared numeric versions within the same indexed
    # document identity. This is not a claim about unseen corpus revisions.
    versions={}
    version_eligible={'CONTEXT_ONLY','CORROBORATES','CONTRADICTS','NOT_FULLY_VERIFIABLE'}
    for entry in entries:
        v=entry['version']
        if v and re.fullmatch(r'v?\d+',v,re.I) and entry['disposition'] in version_eligible:
            key=entry['source']['document_id'];versions[key]=max(versions.get(key,0),int(v.lstrip('vV')))
    for entry in entries:
        v=entry['version'];key=entry['source'].get('document_id')
        if v and re.fullmatch(r'v?\d+',v,re.I) and int(v.lstrip('vV'))<versions.get(key,0) and entry['disposition'] in version_eligible:
            entry['disposition']='OLDER_RETRIEVED_VERSION'
            entry['version_status']='OLDER_THAN_ANOTHER_RETRIEVED_DECLARED_VERSION'
    return {'schema_version':'opslens.document-corroboration.v1','sources':entries,'database_measurements':db,
        'limitations':['Retrieved text is not evidence of causation.','Index dates are inferred, and authoritative version history is unavailable; current-version certification is not possible.','Only explicit Measurement JSON claims with matching metric, period, source, unit and population are numerically comparable. Other prose remains context.','Retrieval is bounded to five passages and cannot certify corpus completeness.'],
        'causal_claim':False}

async def corroborate(question,result,search,state):
    if not REQUEST.search(question) or result.get('executable') is not True or result.get('causal_claim') is not False:return result
    result=deepcopy(result)
    if result.get('document_history_limit_reached'):
        message='Document check history limit reached; start a new investigation for another retrieval.'
        if message not in result['document_evidence']['limitations']:
            result['document_evidence']['limitations'].append(message)
        result['orchestration']=state.snapshot('DOCUMENT_HISTORY_LIMIT')
        return result
    try:
        state.begin('document_corroboration','User requested document corroboration of validated measurements')
        query=question[:2000]
        hits=await state.read('knowledge:'+query,lambda:search(query))
        evidence=assess(hits,result,query)
        evidence['status']='ASSESSED' if hits else 'NO_DOCUMENT_EVIDENCE'
        state.trace[-1]['decision']='ASSESSED'
    except Exception as exc:
        evidence={'schema_version':'opslens.document-corroboration.v1','status':'BUDGET_STOP' if isinstance(exc,(BudgetStop,TimeoutError)) else 'RETRIEVAL_UNAVAILABLE',
            'error_type':type(exc).__name__,'sources':[],'causal_claim':False,'limitations':['Document check did not complete; validated database findings are retained.']}
        if state.trace and state.trace[-1]['capability']=='document_corroboration':state.trace[-1]['decision']='STOPPED'
    result['document_evidence']=evidence
    counts={k:sum(s['disposition']==k for s in evidence['sources']) for k in ('CORROBORATES','CONTRADICTS','CONTEXT_ONLY','OUTDATED_OR_PROVISIONAL')}
    summary=(f"Document cross-check: {counts['CORROBORATES']} corroborating passages, {counts['CONTRADICTS']} conflicting passages, {counts['CONTEXT_ONLY']} context-only passages and {counts['OUTDATED_OR_PROVISIONAL']} outdated or provisional passages."
        if evidence['sources'] else 'No usable document corroboration was established; the database findings remain available.')
    evidence['summary']=summary
    result['conclusions']=[*result.get('conclusions',[]),summary]
    result['orchestration']=state.snapshot(evidence['status'])
    return result
