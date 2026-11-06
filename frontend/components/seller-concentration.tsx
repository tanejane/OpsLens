import type { NormalizedInvestigation } from "../lib/investigation";
import { InvestigationEvidence } from "./investigation-evidence";
type Row={seller_id:string;orders:number;eligible:number;late:number;late_rate_pct:string|null;share_of_single_seller_late_pct:string|null};
type Proof={sellers:Row[];buckets:Record<string,{orders:number;eligible:number;late:number}>;methodology:string;source:string};
export function SellerConcentration({report,mode}:{report:NormalizedInvestigation;mode:"Business"|"Analyst"}) {
  const payload=report.canonicalRecord.payload as unknown as {reason:string;conclusions?:string[];seller_analysis?:Proof;limitations:string[];orchestration?:unknown};
  const proof=payload.seller_analysis;
  const pct=(v:string|null)=>v==null?'Unavailable':`${Number(v).toFixed(2)}%`;
  return <article className="report"><section className="report-section"><h2>Where are late orders concentrated?</h2><p>{payload.reason}</p>{payload.conclusions?.map(s=><p key={s}>{s}</p>)}
    {proof ? <><p>Compare counts alongside late rates: high-volume sellers can have more late orders without having a higher late rate. Review these cohorts before deciding where to investigate further.</p>
    <h3>Largest late-order counts · single-seller orders</h3><p>Top 10 by count; all validated seller rows remain in the evidence. Ties are ordered by seller ID.</p>
    <svg viewBox={`0 0 700 ${Math.max(50,proof.sellers.slice(0,10).length*42)}`} style={{width:'100%'}} role="img" aria-label="Late order counts by seller for single-seller orders">{proof.sellers.slice(0,10).map((s,i)=><g key={s.seller_id}><text x="0" y={i*42+25} fontSize="10">{s.seller_id}</text><rect x="260" y={i*42+8} height="25" width={350*s.late/Math.max(1,proof.sellers[0]?.late??0)} fill="#b47b54"/><text x="630" y={i*42+25}>{s.late}</text></g>)}</svg>
    <table><thead><tr><th>Seller</th><th>Late orders</th><th>Eligible orders</th><th>Late rate</th><th>Share of single-seller late orders</th></tr></thead><tbody>{(mode==='Analyst'?proof.sellers:proof.sellers.slice(0,10)).map(s=><tr key={s.seller_id}><td>{s.seller_id}</td><td>{s.late}</td><td>{s.eligible}</td><td>{pct(s.late_rate_pct)}</td><td>{pct(s.share_of_single_seller_late_pct)}</td></tr>)}</tbody></table>
    <h3>Orders included and excluded from seller ranking</h3>{Object.entries(proof.buckets).map(([k,b])=><p key={k}>{k.replaceAll('_',' ')}: {b.orders} orders; {b.eligible} timestamp-eligible; {b.late} late.</p>)}
    {mode==='Analyst'&&<><p>{proof.methodology}</p><p>Sources: {proof.source}</p><details><summary>Investigation steps</summary><pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(payload.orchestration,null,2)}</pre></details></>}
    </> : <p>Seller-level findings are not established. The validated overall delivery result is retained above.</p>}
    <ul>{payload.limitations.map(s=><li key={s}>{s}</li>)}</ul></section><InvestigationEvidence report={report} mode={mode}/></article>;
}
