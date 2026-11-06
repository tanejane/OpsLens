"""Interactive Phase 4B.3 governed relationships preview. No arbitrary joins."""
import asyncio, json, os
from mcp import Client
from google import genai
from google.genai import types
from agent.phase4b1_semantic_playground import call, column_types
from agent.phase4b3_relationship_governance import CONTRACTS, RelationshipRequest, compile_relationship
from mcp_server.server import mcp

async def ask(question):
    key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not key: raise RuntimeError('Set GEMINI_API_KEY locally')
    payload={'question':question,'supported_metric_dimension_pairs':[{'metric':m,'dimension':d,'meaning':c.meaning} for (m,d),c in CONTRACTS.items()]}
    ai=genai.Client(api_key=key)
    reply=ai.models.generate_content(model=os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite'),contents=json.dumps(payload),config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_schema=RelationshipRequest,system_instruction='Choose the exact requested metric and dimension, do not substitute alternatives. Only use explicit dates in the question. Lowest = asc; highest/most = desc. No SQL.'))
    req=RelationshipRequest.model_validate_json(reply.text)
    print('\nMETRIC REQUEST:',req.model_dump_json(indent=2))
    contract=CONTRACTS.get((req.metric,req.dimension))
    if contract is None: raise ValueError('Unsupported relationship: cannot compute this safely yet')
    relations=set(contract.sources)|({'commerce.orders'} if req.dimension=='category' else set())
    async with Client(mcp) as client:
        live={}
        for rel in relations:
            schema,name=rel.split('.')
            live[rel]=column_types(await call(client,'describe_relation',{'schema':schema,'relation':name}))
        # describe_relation can reject a source not in the MCP catalog. The compiler
        # additionally checks all required live columns and exact allowlisted paths.
        sql,meta=compile_relationship(req,live,set(live))
        print('\nGOVERNED SQL:',sql)
        result=await call(client,'run_readonly_sql',{'query':sql,'purpose':f'Governed relationship metric: {question[:250]}','expected_grain':meta.grain,'max_rows':req.limit})
        print('\nMEASURED RESULTS:',json.dumps(result,indent=2,default=str))
        print('\nDEFINITION:',meta.meaning)
        print('SOURCES:', ', '.join(meta.sources + (('commerce.orders',) if req.dimension=='category' else ())))
        print('LIMITATION: descriptive; order-key uniqueness/cardinality and total reconciliation require independent live audits; no causal attribution.')
async def main():
    print('OpsLens 4B.3 — approved relationship analytics preview')
    while True:
        question=input('\nOpsLens > ').strip()
        if not question or question.lower() in ('exit','quit'): break
        try: await ask(question)
        except Exception as ex:
            while isinstance(ex,BaseExceptionGroup) and ex.exceptions: ex=ex.exceptions[0]
            print('BLOCKED/FAILED (not evidence):',type(ex).__name__,str(ex)[:500])
if __name__=='__main__': asyncio.run(main())
