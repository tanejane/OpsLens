import type {NormalizedInvestigation} from '../lib/investigation';
type Source={source:{filename?:string;document_id?:string;chunk_id?:string;source_date?:string;trust_level?:string;content?:string};disposition:string;version:string|null;version_status:string;date_status:string;content_sha256:string;comparisons:unknown[]};
type Evidence={summary:string;status:string;sources:Source[];limitations?:string[]};
export function DocumentEvidence({report,mode}:{report:NormalizedInvestigation;mode:'Business'|'Analyst'}){
 const evidence=report.canonicalRecord.payload.document_evidence as Evidence|undefined;
 if(!evidence)return null;
 const labels:Record<string,string>={CORROBORATES:'Agrees with the measured figures',CONTRADICTS:'Conflicts with the measured figures',CONTEXT_ONLY:'Relevant context; not numerically verified',OUTDATED_OR_PROVISIONAL:'Outdated or provisional',OLDER_RETRIEVED_VERSION:'Older than another retrieved version',NOT_FULLY_VERIFIABLE:'Claim could not be fully compared'};
 return <section className="report-section"><h2>Document cross-check</h2><p>{evidence.summary}</p><p>Document claims do not establish causes. Current-version certification is unavailable.</p>
 {evidence.sources.filter(s=>mode==='Analyst'||!!labels[s.disposition]).map((s,i)=><div key={`${s.source.chunk_id}-${i}`}><h3>{s.source.filename}</h3><p>{labels[s.disposition]??'Excluded from the evidence comparison'} · {s.source.source_date??'Date unknown'}</p>
 {mode==='Business'&&s.disposition==='CONTRADICTS'&&<p>Use the governed database measurement for this scope; resolve the conflicting document before relying on it.</p>}
 {mode==='Business'&&s.disposition==='CONTEXT_ONLY'&&<><p>Document excerpt (not independently verified):</p><blockquote>{s.source.content?.slice(0,400)}{(s.source.content?.length??0)>400?'…':''}</blockquote></>}
 {mode==='Analyst'&&<details><summary>Passage, provenance and comparison</summary><p>Document {s.source.document_id}; chunk {s.source.chunk_id}; trust {s.source.trust_level}; version {s.version??'unknown'} ({s.version_status}); date {s.date_status}; disposition {s.disposition}</p><blockquote style={{whiteSpace:'pre-wrap'}}>{s.source.content}</blockquote><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(s.comparisons,null,2)}</pre><p>Content SHA-256: {s.content_sha256}</p></details>}</div>)}
 {mode==='Analyst'&&<ul>{evidence.limitations?.map(s=><li key={s}>{s}</li>)}</ul>}</section>;
}
