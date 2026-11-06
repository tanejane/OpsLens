"""Read-only MCP checks of semantic-map contracts. Does NOT grant execution permissions."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENT = re.compile(r'^[a-z_][a-z0-9_]*$')

class AuditError(ValueError):
    pass

def ident(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise AuditError(f'Unsafe identifier: {value!r}')
    return '"'+value+'"'

def source_sql(source):
    parts = source.split('.')
    if len(parts) != 2 or parts[0] not in {'commerce','catalog','finance','semantic','cx','operations','inventory','marketing','behavior'}:
        raise AuditError(f'Unapproved source: {source}')
    return '.'.join(map(ident, parts))

def key_expr(keys):
    if not keys: raise AuditError('Missing grain')
    return ', '.join(ident(k) for k in keys)

def uniqueness_sql(src, keys):
    table=source_sql(src)
    expr=key_expr(keys)
    null_cond=' OR '.join(f'{ident(k)} IS NULL' for k in keys)
    return (f'SELECT COUNT(*) AS total_rows, COUNT(*) FILTER (WHERE {null_cond}) AS null_key_rows, '
            f'COUNT(*) - COUNT(DISTINCT ({expr})) AS repeated_key_rows FROM {table}')

def relationship_sql(rel, side):
    """Check declared FK-side match and cardinality without multiplying join rows."""
    left,right=source_sql(rel['left']),source_sql(rel['right'])
    lk,rk=ident(rel['left_key']),ident(rel['right_key'])
    if side not in ('left','right'): raise AuditError('Unknown side')
    if side=='right':
        return (f'SELECT COUNT(*) AS child_rows, COUNT(*) FILTER (WHERE c.{rk} IS NULL) AS null_keys, '
                f'COUNT(*) FILTER (WHERE c.{rk} IS NOT NULL AND NOT EXISTS '
                f'(SELECT 1 FROM {left} p WHERE p.{lk}=c.{rk})) AS unmatched_rows '
                f'FROM {right} c')
    return (f'SELECT COUNT(*) AS left_rows, COUNT(*) FILTER (WHERE p.{lk} IS NULL) AS null_keys, '
            f'COUNT(*) FILTER (WHERE p.{lk} IS NOT NULL AND NOT EXISTS '
            f'(SELECT 1 FROM {right} c WHERE c.{rk}=p.{lk})) AS unmatched_rows '
            f'FROM {left} p')

def coverage_sql(src, col, data_type):
    table=source_sql(src); c=ident(col)
    native = {'date','timestamp without time zone','timestamp with time zone'}
    if data_type in native: expr=c
    elif data_type in {'text','character varying','character'} and (col.endswith('_date') or col.endswith('_timestamp') or col == 'business_date'):
        expr=f"CASE WHEN pg_input_is_valid(NULLIF(BTRIM({c}),''), 'timestamp without time zone') THEN NULLIF(BTRIM({c}),'')::timestamp ELSE NULL END"
    else: raise AuditError(f'Unsafe or unsupported date column: {src}.{col} ({data_type})')
    return f'SELECT MIN({expr}) AS min_date, MAX({expr}) AS max_date, COUNT(*) AS total_rows, COUNT({expr}) AS dated_rows FROM {table}'

def classify_key(row):
    n=int(row.get('total_rows',0)); nulls=int(row.get('null_key_rows',0)); repeated=int(row.get('repeated_key_rows',0))
    # Valid even for empty source? No: cannot verify uniqueness over nonexistent evidence.
    return 'VERIFIED' if n>0 and not nulls and not repeated else ('UNKNOWN_EMPTY' if n==0 else 'REJECTED')

def classify_relationship(rel, left_status, right_status, left_row, right_row):
    if left_status!='VERIFIED' and rel['cardinality'] in ('one_to_many','one_to_one'): return 'UNVERIFIED_PARENT_KEY'
    if right_status!='VERIFIED' and rel['cardinality'] in ('many_to_one','one_to_one'): return 'UNVERIFIED_TARGET_KEY'
    if int(right_row.get('unmatched_rows',0))>0: return 'UNMATCHED_FOREIGN_KEYS'
    if int(right_row.get('null_keys',0))>0: return 'NULL_FOREIGN_KEYS'
    if int(right_row.get('child_rows',0))==0: return 'UNKNOWN_EMPTY'
    return 'STRUCTURALLY_VERIFIED'

def unwrap(response, tool):
    p=getattr(response,'structured_content',None)
    if not isinstance(p,dict) or p.get('ok') is not True:
        raise AuditError(f'MCP {tool} unavailable: {str(p)[:400]}')
    return p['data']

def first_row(data):
    rows=data.get('rows') if isinstance(data,dict) else None
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict):
        raise AuditError('Unexpected SQL response rows')
    return rows[0]

async def audit(client, catalog, source_ids=None):
    async def tool(name,args): return unwrap(await client.call_tool(name,args),name)
    async def sql(query,purpose):
        return first_row(await tool('run_readonly_sql',{'query':query,'purpose':purpose,'expected_grain':'single aggregate audit row','max_rows':1,'timeout_ms':5000}))
    sources = {s['id']:s for s in catalog['sources']}
    requested=set(source_ids or sources)
    # Restrict audits to explicit approved contract sources.
    if not requested.issubset(sources): raise AuditError('Unknown source requested')
    for r in catalog['relationships']:
        if r['left'] in requested or r['right'] in requested: requested.update([r['left'],r['right']])
    report={'version':'4b4.1','disclaimer':'Diagnostics only; no joins are automatically approved for analytical measures.', 'sources':{},'relationships':{}}
    for sid in sorted(requested):
        s=sources[sid]; out={'declared_scope':s.get('scope'),'declared_grain':s.get('grain'),'checks':{}}
        report['sources'][sid]=out
        try:
            meta=await tool('describe_relation',dict(zip(('schema','relation'),sid.split('.'))))
            columns={str(x.get('column_name')):str(x.get('data_type')) for x in meta}
            out['columns_verified']=set(s.get('columns',[])).issubset(columns)
            out['missing_columns']=sorted(set(s.get('columns',[]))-set(columns))
            out['live_column_count']=len(columns)
            if all(k in columns for k in s.get('grain',[])):
                try:
                    row=await sql(uniqueness_sql(sid,s['grain']),'Verify key uniqueness and NULL keys for '+sid)
                    out['checks']['grain']={'status':classify_key(row),'result':row}
                except Exception as exc: out['checks']['grain']={'status':'ERROR','error':str(exc)}
            else: out['checks']['grain']={'status':'MISSING_COLUMNS'}
            col=s.get('date_column')
            if col and col in columns:
                try:
                    row=await sql(coverage_sql(sid,col,columns[col]),'Profile date coverage for '+sid)
                    out['checks']['coverage']={'status':'MEASURED','result':row,'declared_coverage':s.get('coverage')}
                except Exception as exc: out['checks']['coverage']={'status':'ERROR','error':str(exc)}
            elif col: out['checks']['coverage']={'status':'MISSING_DATE_COLUMN'}
            else: out['checks']['coverage']={'status':'NO_DATE_COLUMN'}
        except Exception as exc:
            out['metadata_error']=str(exc)
    for r in catalog['relationships']:
        if r['left'] not in requested or r['right'] not in requested: continue
        out={'left':r['left'],'right':r['right'],'cardinality':r['cardinality'],'fanout_risk':r.get('fanout_risk',True)}
        report['relationships'][r['id']]=out
        left=report['sources'][r['left']];right=report['sources'][r['right']]
        if r['left_key'] not in (left.get('missing_columns') or []) and r['right_key'] not in (right.get('missing_columns') or []) and 'metadata_error' not in left and 'metadata_error' not in right:
            try:
                # Check target uniqueness for many_to_one, join-key uniqueness may differ from composite grain.
                leftkey=await sql(uniqueness_sql(r['left'],[r['left_key']]),'Relationship left-key cardinality '+r['id'])
                rightkey=await sql(uniqueness_sql(r['right'],[r['right_key']]),'Relationship right-key cardinality '+r['id'])
                unmatched=await sql(relationship_sql(r,'right'),'Foreign-key match audit '+r['id'])
                out.update({'left_key':leftkey,'right_key':rightkey,'foreign_key':unmatched})
                out['status']=classify_relationship(r,classify_key(leftkey),classify_key(rightkey),{},unmatched)
                if out['status']=='STRUCTURALLY_VERIFIED':
                    out['warning']='Join path keys verified; measure fanout and business semantics still require validation.'
            except Exception as exc:out.update(status='ERROR',error=str(exc))
        else:out['status']='MISSING_METADATA'
    return report

async def live_main(output):
    from mcp import Client
    from mcp_server.server import mcp
    catalog=json.loads((ROOT/'config'/'phase4b4_semantic_map.json').read_text(encoding='utf8'))
    async with Client(mcp) as client:
        result=await audit(client,catalog)
    path=Path(output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,default=str),encoding='utf8')
    print('Live semantic map audit saved:',path)
    for sid,v in result['sources'].items():
        print('SOURCE',sid,'grain:',v['checks'].get('grain',{}).get('status'),'coverage:',v['checks'].get('coverage',{}).get('status'))
    for rid,v in result['relationships'].items(): print('RELATIONSHIP',rid,v['status'])
    print('No relationships have been automatically authorized for arbitrary measures.')
