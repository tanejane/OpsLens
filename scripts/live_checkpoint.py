"""Real MCP/database checkpoint. No mock data or model substitution."""
import asyncio,json,time
from pathlib import Path
from mcp import Client
from mcp_server.server import mcp
from scripts.phase5_1_playground import mcp_query
from agent.delivery_review_comparison import investigate as comparison
from agent.seller_concentration import initial as seller
from agent.evidence_followup import extend
from agent.investigation_state import InvestigationState
from agent.investigation_result import canonical_result,evidence_archive
from agent.phase4c3_investigation import investigate as finance,InvestigationRequest

async def main():
    results=[]
    async with Client(mcp) as client:
        for name,operation in [
            ('finance',lambda reader:finance(InvestigationRequest('2018-02-01','2018-03-01','2018-03-01','2018-04-01'),reader)),
            ('delivery_march',lambda reader:comparison('2018-03-01','2018-04-01',reader)),
            ('seller_march',lambda reader:seller('2018-03-01','2018-04-01',reader)),
            ('seller_february',lambda reader:seller('2018-02-01','2018-03-01',reader))]:
            trace=[];start=time.monotonic();state=InvestigationState();state.begin('initial','Live governed execution with explicit dates; Gemini not used')
            async def reader(sql,purpose):
                return await state.read(sql,lambda:mcp_query(client,sql,purpose,trace=trace))
            with evidence_archive() as archive:
                try:
                    initial=await operation(reader);state.trace[-1]['decision']='VALIDATED'
                    result=await extend(initial,reader,state)
                    result.update(execution_trace=trace,validated_evidence=archive)
                    entry={'name':name,'status':'LIVE_VALIDATED','canonical_result':canonical_result(name,result)}
                except Exception as exc:
                    entry={'name':name,'status':'FAILED','error_type':type(exc).__name__,'error':str(exc), 'execution_trace':trace}
            entry['latency_seconds']=round(time.monotonic()-start,3);results.append(entry)
            Path('reports/live_database_checkpoint.json').write_text(json.dumps({'scope':'Real MCP and PostgreSQL; explicit governed requests, no Gemini or HTTP substitution','results':results},indent=2,default=str),encoding='utf-8')
            print(name,entry['status'],entry['latency_seconds'],flush=True)

if __name__=='__main__':asyncio.run(main())
