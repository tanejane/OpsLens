import type {NormalizedInvestigation} from '../lib/investigation';

export function InvestigationTimeline({report,mode}:{report:NormalizedInvestigation;mode:'Business'|'Analyst'}){
 if(mode!=='Analyst')return null;
 const payload=report.canonicalRecord.payload;
 const audit=payload.observability as {run_id:string;latency_ms:number;validation_decision:string;stop_reason:string;persistence:string;evidence:unknown[];model_metadata:unknown}|undefined;
 if(!audit)return null;
 const session=(payload.context_provenance as {session_id?:string}|undefined)?.session_id;
 const calls=(payload.execution_trace??[]) as {tool:string;latency_ms?:number;outcome?:string;error_type?:string}[];
 const steps=(payload.orchestration as {trace?:{step:number;capability:string;reason:string;decision:string}[]}|undefined)?.trace??[];
 return <details className="trace-details"><summary>Investigation timeline and replay</summary>
  <p>Run {audit.run_id} · {audit.latency_ms} ms · {audit.validation_decision}</p>
  <p>Stop reason: {audit.stop_reason}. Trace storage: {audit.persistence}.</p>
  <ol>{steps.map((step,i)=><li key={i}>{step.capability}: {step.decision} — {step.reason}</li>)}</ol>
  <ol>{calls.map((call,i)=><li key={i}>{call.tool} — {call.outcome??'Recorded'}{call.latency_ms!==undefined?` (${call.latency_ms} ms)`:''}{call.error_type?` · ${call.error_type}`:''}</li>)}</ol>
  <p>Replay returns the saved canonical evidence without new model, MCP or database calls. It does not revalidate against current data. Access expires with the session or trace retention.</p>
  {session&&audit.persistence==='SAVED'&&<a href={`/api/investigation-sessions/${encodeURIComponent(session)}/runs/${encodeURIComponent(audit.run_id)}/replay`} target="_blank" rel="noreferrer">Open saved evidence replay (JSON)</a>}
  <details><summary>Validation references and model metadata</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify({evidence:audit.evidence,model:audit.model_metadata},null,2)}</pre></details>
 </details>;
}
