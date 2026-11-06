"""Phase 4B.2 metric-first CLI; deliberately refuses unsupported metrics/joins."""
import asyncio, json, os
from mcp import Client
from google import genai
from google.genai import types
from agent.phase4b1_semantic_playground import call, column_types
from agent.phase4b2_metric_governance import METRICS, MetricRequest, compile_metric, QueryRejected
from mcp_server.server import mcp

async def ask(question):
    key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key: raise RuntimeError('Set GEMINI_API_KEY in your current terminal')
    # The model receives only executable metric IDs, not SQL, column expressions or secrets.
    prompt={'question':question,'available_metrics':{k:{'definition':v.meaning,'dimensions':v.dimensions,'grain':v.grain} for k,v in METRICS.items()},'instructions':'If a necessary join/dimension is not available, you may return it as a requested dimension; compiler will block and explain. Do not substitute profit for margin. Do not fabricate date ranges.'}
    client_ai=genai.Client(api_key=key)
    response=client_ai.models.generate_content(model=os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite'),contents=json.dumps(prompt),config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_schema=MetricRequest,system_instruction='Choose metric ID and requested dimensions faithfully. Convert explicit dates to half-open ranges. For lowest choose asc; highest choose desc. No SQL, formulas, causal claims or invented metrics.'))
    spec=MetricRequest.model_validate_json(response.text)
    print('\nMETRIC REQUEST:',spec.model_dump_json(indent=2))
    if spec.metric not in METRICS: raise QueryRejected('Unsupported metric, no safe approximation')
    metric=METRICS[spec.metric]
    async with Client(mcp) as client:
        schema,relation=metric.source.split('.')
        metadata=column_types(await call(client,'describe_relation',{'schema':schema,'relation':relation}))
        sql=compile_metric(spec,metadata,{metric.source})
        print('\nGOVERNED SQL:',sql)
        result=await call(client,'run_readonly_sql',{'query':sql,'purpose':f'Governed metric analysis: {question[:250]}','expected_grain':metric.grain+' aggregated by '+str(spec.dimensions),'max_rows':spec.limit})
        print('\nMEASURED RESULT:',json.dumps(result,indent=2,default=str))
        print('\nMETRIC DEFINITION:',metric.meaning,'\nSOURCE:',metric.source,'\nGRAIN:',metric.grain)
        print('LIMITATION: Descriptive metric calculation only; no causal attribution or unapproved joins.')
async def main():
    print('OpsLens Phase 4B.2 — governed metric playground (limited preview)')
    while True:
        question=input('\nOpsLens > ').strip()
        if not question or question.lower() in ('exit','quit'): break
        try: await ask(question)
        except Exception as exc:
            # Unwrap anyio task-group exception in a concise, safe form.
            node=exc
            while isinstance(node,BaseExceptionGroup) and node.exceptions:
                node=node.exceptions[0]
            print('BLOCKED/FAILED (no evidence):',type(node).__name__,str(node)[:400])
if __name__=='__main__': asyncio.run(main())
