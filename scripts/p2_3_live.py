"""Read-only live MCP verification, not a Gemini/HTTP journey."""
import asyncio,json,time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('.env',override=True)

async def main():
 from mcp import Client
 from mcp_server.server import mcp
 from agent.phase4b57_nl_dynamic_finance import mcp_query
 from agent.refund_concentration import initial
 from agent.evidence_followup import extend
 from agent.investigation_state import InvestigationState
 from agent.investigation_result import canonical_result,evidence_archive
 from investigation_traces import redact
 reports=[]
 for start,end in [('2018-07-01','2018-08-01'),('2019-07-01','2019-08-01')]:
  trace=[];began=time.monotonic()
  try:
   async with Client(mcp) as client:
    state=InvestigationState();state.begin('initial','Live governed refund verification')
    async def reader(sql,purpose):return await state.read(sql,lambda:mcp_query(client,sql,purpose,trace=trace))
    with evidence_archive() as archive:
     result=await initial(start,end,reader)
     result=await extend(result,reader,state)
     result.update(execution_trace=trace,validated_evidence=archive)
     reports.append({'status':'COMPLETED','latency_seconds':round(time.monotonic()-began,3),'canonical_result':canonical_result('Where are refunds concentrated for purchases in '+start,result)})
  except Exception as exc:
   reports.append({'status':'FAILED','error_type':type(exc).__name__,'latency_seconds':round(time.monotonic()-began,3),'execution_trace':redact(trace)})
  Path('reports/p2_3_live.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
  print(reports[-1]['status'],start,flush=True)

if __name__=='__main__':asyncio.run(main())
