import type {NormalizedInvestigation} from '../lib/investigation';
import {InvestigationEvidence} from "./investigation-evidence";
type Counts={orders:number;returned_orders:number;refunded_orders:number;events:number;refund_amount:string;return_rate_pct:string|null;multi_item_orders?:number};
type Seller=Counts&{seller_id:string;share_of_all_refunds_pct:string|null};
export function RefundConcentration({report,mode}:{report:NormalizedInvestigation;mode:'Business'|'Analyst'}){
 const payload=report.canonicalRecord.payload as unknown as {reason:string;conclusions?:string[];limitations:string[];refund_intent:boolean;evidence:{population:Counts;source_unlinked_events:number;source_types:string[]};refund_analysis?:{sellers:Seller[];buckets:Record<string,Counts>;methodology:string;source:string}};
 const p=payload.evidence.population,proof=payload.refund_analysis;
 const num=(v:string|null)=>v==null?'Unavailable':Number(v).toLocaleString(undefined,{maximumFractionDigits:2});
 return <article className="report"><section className="report-section"><h2>Where are order-linked refunds concentrated?</h2><p>{payload.reason}</p>
 <div className="kpi-grid"><div><h3>Linked refunds</h3><strong>{num(p.refund_amount)}</strong></div><div><h3>Orders with returns</h3><strong>{p.returned_orders} / {p.orders}</strong><p>{num(p.return_rate_pct)}{p.return_rate_pct!==null?'%':''}</p></div><div><h3>Orders with positive refunds</h3><strong>{p.refunded_orders}</strong></div></div>
 {proof?<><h3>Largest refund amounts · single-seller orders</h3><p>Top 10 sellers by refund amount. Share uses all linked refunds, including shared and unmapped orders.</p>
 <svg viewBox={`0 0 700 ${Math.max(50,proof.sellers.slice(0,10).length*42)}`} style={{width:'100%'}} role="img" aria-label="Order-linked refund amounts by exclusive seller cohort">{proof.sellers.slice(0,10).map((s,i)=><g key={s.seller_id}><text x="0" y={i*42+25} fontSize="10">{s.seller_id}</text><rect x="260" y={i*42+8} height="25" width={300*Number(s.refund_amount)/Math.max(1,Number(proof.sellers[0]?.refund_amount??0))} fill="#b47b54"/><text x="575" y={i*42+25}>{num(s.refund_amount)}</text></g>)}</svg>
 <table><thead><tr><th>Seller</th><th>Refund amount</th><th>Share of all refunds</th><th>Orders with returns / purchased</th><th>Return rate</th></tr></thead><tbody>{(mode==='Analyst'?proof.sellers:proof.sellers.slice(0,10)).map(s=><tr key={s.seller_id}><td>{s.seller_id}</td><td>{num(s.refund_amount)}</td><td>{num(s.share_of_all_refunds_pct)}{s.share_of_all_refunds_pct!==null?'%':''}</td><td>{s.returned_orders} / {s.orders}</td><td>{num(s.return_rate_pct)}{s.return_rate_pct!==null?'%':''}</td></tr>)}</tbody></table>
 <h3>Attribution coverage</h3>{Object.entries(proof.buckets).map(([k,b])=><p key={k}>{k.replaceAll('_',' ')}: {b.orders} orders, {b.returned_orders} with returns; refunds {num(b.refund_amount)}.</p>)}
 <p>Use refund amounts to prioritize review, then compare return rates and order volume. Inspect the linked return records before deciding on action; these cohorts do not identify seller responsibility.</p>
 {mode==='Analyst'&&<><p>{proof.methodology}</p><p>Sources: {proof.source}</p><details><summary>Exact calculations, multi-item counts and attribution</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(proof,null,2)}</pre></details></>}
 </>:<p>{payload.refund_intent&&p.returned_orders>0?'Seller concentration was not established; the validated order-level findings remain available.':'The order-level measurement answers this request; no additional seller query was needed.'}</p>}
 {mode==='Analyst'&&<p>Source-wide unlinked return events: {payload.evidence.source_unlinked_events} (outside the cohort denominator). Recorded source types: {payload.evidence.source_types.join(', ')}.</p>}
 <ul>{payload.limitations.map(s=><li key={s}>{s}</li>)}</ul></section><InvestigationEvidence report={report} mode={mode}/></article>;
}
