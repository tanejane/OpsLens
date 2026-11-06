"""Interactive guarded SQL analysis, no causal inference or hidden truth access."""
from __future__ import annotations
import asyncio, json, os, sys
from copy import deepcopy
from google import genai
from google.genai import types
from mcp import Client
from pydantic import ValidationError
from mcp_server.server import mcp
from agent.phase4b1_semantic_query import QuerySpec, QueryRejected, compile_query, previous_window

async def call(client, name, args, *, trace=None):
    import time
    started=time.monotonic()
    try:
        response = await client.call_tool(name,args)
    except BaseException as exc:
        if trace is not None:
            trace.append({'tool':name,'arguments':deepcopy(args),'latency_ms':round((time.monotonic()-started)*1000,3),
                'outcome':'FAILED','error_type':type(exc).__name__})
        raise
    payload = response.structured_content
    if trace is not None:
        trace.append({'tool': name, 'arguments': deepcopy(args), 'response': deepcopy(payload),
            'latency_ms':round((time.monotonic()-started)*1000,3),
            'outcome':'RETURNED' if isinstance(payload,dict) and payload.get('ok') is True else 'REJECTED'})
    if not isinstance(payload,dict) or payload.get('ok') is not True:
        raise RuntimeError(f"MCP {name} failed: {payload}")
    return payload['data']

def extract_relations(data):
    # MCP discover_schema may return names as strings or objects.
    if isinstance(data,dict):
        for key in ('relations','items','tables'):
            if isinstance(data.get(key),list): data=data[key]; break
    if not isinstance(data,list): raise RuntimeError('Unrecognized MCP schema response')
    return data

def column_types(data):
    if isinstance(data,dict):
        for key in ('columns','items'):
            if isinstance(data.get(key),list): data=data[key]; break
    if not isinstance(data,list): raise RuntimeError('Unrecognized describe_relation response')
    columns={}
    for item in data:
        if not isinstance(item,dict): raise RuntimeError('Malformed column metadata')
        name=item.get('column_name') or item.get('name')
        typ=item.get('data_type') or item.get('type') or item.get('udt_name')
        if not name or not typ: raise RuntimeError('Missing column name or type')
        columns[str(name)] = str(typ)
    return columns

async def run_question(question):
    if not os.getenv('GEMINI_API_KEY') and not os.getenv('GOOGLE_API_KEY'):
        print('Set GEMINI_API_KEY in this PowerShell session.'); return
    async with Client(mcp) as client:
        domain_data=await call(client,'discover_domains',{})
        domain_list = domain_data.get('domains',domain_data) if isinstance(domain_data,dict) else domain_data
        domains=[]
        for d in domain_list:
            if isinstance(d,str): domains.append(d)
            elif isinstance(d,dict):
                val=d.get('domain') or d.get('name')
                if val: domains.append(val)
        if not domains: raise RuntimeError('MCP provided no domain names')
        allowed=set()
        for domain in domains:
            if domain not in {'commerce','catalog','operations','finance','marketing','inventory','cx','behavior','semantic'}: continue
            rows=extract_relations(await call(client,'discover_schema',{'domain':domain}))
            for row in rows:
                if isinstance(row,str):
                    relation=row if '.' in row else domain+'.'+row
                else:
                    name=row.get('relation_name') or row.get('table_name') or row.get('name') or row.get('relation')
                    if not name: continue
                    relation=name if '.' in str(name) else domain+'.'+str(name)
                if relation.startswith(domain+'.'): allowed.add(relation)
        if not allowed: raise RuntimeError('No approved relations discovered')
        # Stage 1 is metadata discovery; keep the model from inventing relations.
        model=os.getenv('OPSLENS_GEMINI_MODEL','gemini-3.5-flash-lite')
        g=genai.Client(api_key=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))
        context={'question':question,'approved_relations':sorted(allowed)}
        response=g.models.generate_content(model=model,contents=json.dumps(context),config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_schema={'type':'OBJECT','properties':{'relation':{'type':'STRING'},'reason':{'type':'STRING'}},'required':['relation','reason']} ,system_instruction='Choose ONE relevant approved relation. Never invent a relation. No SQL. If question requires multiple relations choose the first necessary measurable outcome relation.'))
        selection=json.loads(response.text)
        relation=selection['relation']
        if relation not in allowed: raise QueryRejected('Gemini selected an unapproved relation')
        schema, table=relation.split('.')
        columns=column_types(await call(client,'describe_relation',{'schema':schema,'relation':table}))
        # Stage 2: query spec grounded in REAL columns.
        response=g.models.generate_content(model=model,contents=json.dumps({'question':question,'selected_relation':relation,'columns':columns},ensure_ascii=False),config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_schema=QuerySpec,system_instruction=('Propose ONE bounded descriptive SQL query specification using only provided columns. Never write SQL or infer causal explanation. When explicit time period is present, use half-open date range. If question needs joining other tables, choose a useful single-relation first measurement but disclose it is partial. For metric averages use avg; counts use count. Do not compare previous period unless user asks for a trend or change and date is explicit. Do not invent missing columns.')))
        spec=QuerySpec.model_validate_json(response.text)
        if spec.relation!=relation: raise QueryRejected('Model changed relation after metadata grounding')
        sql=compile_query(spec,columns,allowed)
        print('\nPLAN:',spec.model_dump_json(indent=2))
        print('\nGOVERNED SQL:',sql)
        data=await call(client,'run_readonly_sql',{'query':sql,'purpose':f'User-requested descriptive analysis: {question[:300]}','expected_grain':'grouped rows or one aggregate over the selected relation','max_rows':200})
        print('\nMEASURED RESULTS:',json.dumps(data,indent=2,default=str))
        if spec.compare_previous_period:
            prev=previous_window(spec)
            prev_sql=compile_query(prev,columns,allowed)
            old=await call(client,'run_readonly_sql',{'query':prev_sql,'purpose':'Previous-period descriptive comparison','expected_grain':'same aggregate/grouping for preceding period','max_rows':200})
            print('\nPREVIOUS PERIOD:',json.dumps(old,indent=2,default=str))
        print('\nLIMITATION: Descriptive single-relation evidence only. No causal attribution or validated multi-table joins. Confirm cohort and grain before business decisions.')

async def main():
    print('OpsLens Phase 4B.1 — governed semantic query playground (limited preview)')
    while True:
        question=input('\nOpsLens > ').strip()
        if question.lower() in {'exit','quit',''}: break
        try: await run_question(question)
        except (QueryRejected,ValidationError,RuntimeError,ValueError) as exc: print('BLOCKED:',exc)
        except Exception as exc: print('FAILED (not treated as evidence):',type(exc).__name__,str(exc))
if __name__=='__main__': asyncio.run(main())
