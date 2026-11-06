"""Phase 4B.4.2: read-only semantic relationship verification; never grants execution rights.

Uses the existing Phase 4B.4.1 source audit for grain and coverage, then repairs
relationship FK orientation, query timeouts and error classification.
"""
from __future__ import annotations
import json
from pathlib import Path
from agent.phase4b41_live_verifier import (source_sql, ident, AuditError, unwrap, first_row,
    uniqueness_sql, coverage_sql, classify_key)

ROOT=Path(__file__).resolve().parents[1]
TIMEOUT_MS=20000  # Below existing MCP's 30-second hard cap; timeouts never imply success.


def foreign_key_sides(rel):
    """Return (child source/key, parent source/key); orientation is cardinality-dependent."""
    c=rel['cardinality']
    if c in ('one_to_many','one_to_one'):
        return (rel['right'],rel['right_key'],rel['left'],rel['left_key'])
    if c=='many_to_one':
        return (rel['left'],rel['left_key'],rel['right'],rel['right_key'])
    raise AuditError('Unsupported cardinality: '+str(c))


def fk_sql(rel):
    child,ck,parent,pk=foreign_key_sides(rel)
    # Pre-group the parent keys: a future incorrect parent grain cannot multiply counts.
    # Parent-key uniqueness is checked separately before this can be verified.
    return (f'SELECT COUNT(*) AS child_rows, '
            f'COUNT(*) FILTER (WHERE c.{ident(ck)} IS NULL) AS null_fk_rows, '
            f'COUNT(*) FILTER (WHERE c.{ident(ck)} IS NOT NULL AND p.k IS NULL) AS orphan_fk_rows '
            f'FROM {source_sql(child)} c '
            f'LEFT JOIN (SELECT DISTINCT {ident(pk)} AS k FROM {source_sql(parent)} '
            f'WHERE {ident(pk)} IS NOT NULL) p ON c.{ident(ck)} = p.k')


def single_key_sql(source,key):
    t=source_sql(source);k=ident(key)
    return (f'SELECT COUNT(*) AS total_rows, COUNT(*) FILTER (WHERE {k} IS NULL) AS null_key_rows, '
            f'COUNT(*)-COUNT(DISTINCT {k}) AS repeated_key_rows FROM {t}')


def error_status(exc):
    s=str(exc).lower()
    if 'statement timeout' in s or 'querycanceled' in s or 'canceling statement' in s or 'timed out' in s:
        return 'TIMEOUT'
    return 'ERROR'


def judge(rel, key_rows, fk_row):
    """Conservative: only parent uniqueness + zero orphans are required for structural FK.

    NULL FK is reported separately: optional associations can still be structurally sound,
    but not complete. Even VERIFIED does not mean measure-safe or execution-approved.
    """
    child,ck,parent,pk=foreign_key_sides(rel)
    p=key_rows.get(parent)
    if not p: return 'INCONCLUSIVE_MISSING_KEY_AUDIT'
    if int(p['total_rows']) == 0: return 'INCONCLUSIVE_EMPTY_PARENT'
    if int(p['null_key_rows']) or int(p['repeated_key_rows']): return 'REJECTED_PARENT_KEY_NOT_UNIQUE'
    if not fk_row: return 'INCONCLUSIVE_MISSING_FK_AUDIT'
    if int(fk_row['child_rows'])==0: return 'INCONCLUSIVE_EMPTY_CHILD'
    if int(fk_row['orphan_fk_rows'])>0: return 'REJECTED_ORPHANS'
    if int(fk_row['null_fk_rows'])>0: return 'VERIFIED_WITH_NULL_FOREIGN_KEYS'
    return 'STRUCTURALLY_VERIFIED'


def duplicate_grain_advice(source,grain_check):
    if grain_check.get('status')!='REJECTED': return None
    row=grain_check.get('result',{})
    return {'source':source,'repeated_key_rows':row.get('repeated_key_rows'),
            'recommendation':'Inspect duplicate values and source semantics. Do not revise grain or deduplicate automatically.'}


async def source_checks(client,catalog):
    """Only source audits, avoiding the previous verifier's six slow broken join probes."""
    report={'sources':{}}
    async def tool(name,args):return unwrap(await client.call_tool(name,args),name)
    async def sql(query,purpose):
        res=await tool('run_readonly_sql',{'query':query,'purpose':purpose,
              'expected_grain':'one aggregate audit row','max_rows':1,'timeout_ms':TIMEOUT_MS})
        return first_row(res)
    for s in catalog['sources']:
        sid=s['id']
        out={'declared_scope':s.get('scope'),'declared_grain':s.get('grain'),'checks':{}}
        report['sources'][sid]=out
        try:
            metadata=await tool('describe_relation',dict(zip(('schema','relation'),sid.split('.'))))
            columns={str(c.get('column_name')):str(c.get('data_type')) for c in metadata}
            out['live_columns']=sorted(columns)
            out['missing_columns']=sorted(set(s.get('columns',[]))-set(columns))
            out['columns_verified']=not bool(out['missing_columns'])
            grain=s.get('grain',[])
            if grain and all(k in columns for k in grain):
                try:
                    row=await sql(uniqueness_sql(sid,grain),'Check source grain '+sid)
                    out['checks']['grain']={'status':classify_key(row),'result':row}
                except Exception as exc:out['checks']['grain']={'status':error_status(exc),'error':str(exc)[:300]}
            else:out['checks']['grain']={'status':'MISSING_COLUMNS'}
            col=s.get('date_column')
            if col and col in columns:
                try:
                    row=await sql(coverage_sql(sid,col,columns[col]),'Check source coverage '+sid)
                    out['checks']['coverage']={'status':'MEASURED','result':row,'declared_coverage':s.get('coverage')}
                except Exception as exc:out['checks']['coverage']={'status':error_status(exc),'error':str(exc)[:300]}
            else:out['checks']['coverage']={'status':'MISSING_DATE_COLUMN' if col else 'NO_DATE_COLUMN'}
        except Exception as exc:out['metadata_error']=str(exc)[:300]
    return report


async def audit_live(client,catalog):
    base=await source_checks(client,catalog)
    # Preserve base source findings but replace its prior, incorrectly oriented relationship output.
    report={'version':'4b4.2','disclaimer':'Read-only diagnostics. Nothing is automatically authorized for execution.',
            'sources':base['sources'], 'relationships':{}, 'grain_investigations':[]}
    for name,item in report['sources'].items():
        suggestion=duplicate_grain_advice(name,item.get('checks',{}).get('grain',{}))
        if suggestion:report['grain_investigations'].append(suggestion)
    async def query(sql,purpose):
        res=await client.call_tool('run_readonly_sql',{'query':sql,'purpose':purpose,
                  'expected_grain':'one aggregate audit row','max_rows':1,'timeout_ms':TIMEOUT_MS})
        return first_row(unwrap(res,'run_readonly_sql'))
    key_cache={}
    for rel in catalog['relationships']:
        rid=rel['id'];child,ck,parent,pk=foreign_key_sides(rel)
        info={'cardinality':rel['cardinality'],'child':child,'child_key':ck,'parent':parent,'parent_key':pk,
              'fanout_risk':rel.get('fanout_risk',True),'measure_safe':False,'execution_approved':False}
        report['relationships'][rid]=info
        src=report['sources']
        if any('metadata_error' in src.get(x,{}) for x in (child,parent)):
            info['status']='INCONCLUSIVE_MISSING_METADATA';continue
        # Check that live metadata contains both relation keys; avoid relying on declared catalog alone.
        if any(key not in src[s].get('live_columns',[]) for s,key in ((child,ck),(parent,pk))):
            info['status']='INCONCLUSIVE_MISSING_COLUMNS';continue
        try:
            k=(parent,pk)
            if k not in key_cache:
                # Reuse full-grain uniqueness check if identical, avoiding expensive duplicate audits.
                check=src[parent]['checks'].get('grain',{})
                declared=src[parent].get('declared_grain',[])
                if declared==[pk] and check.get('status') in ('VERIFIED','REJECTED','UNKNOWN_EMPTY') and 'result' in check:
                    key_cache[k]=check['result']
                else:key_cache[k]=await query(single_key_sql(parent,pk),'Verify parent join-key uniqueness: '+rid)
            key_rows={parent:key_cache[k]}
            info['parent_key_audit']=key_cache[k]
            # Do not run expensive FK matching if parent itself is invalid.
            pre=judge(rel,key_rows,None)
            if pre.startswith('REJECTED') or pre=='INCONCLUSIVE_EMPTY_PARENT':
                info['status']=pre;continue
            row=await query(fk_sql(rel),'Check foreign keys without measure fanout: '+rid)
            info['foreign_key_audit']=row
            info['status']=judge(rel,key_rows,row)
        except Exception as exc:
            info['status']=error_status(exc)
            info['error']=str(exc)[:500]
    return report


async def main():
    from mcp import Client
    from mcp_server.server import mcp
    catalog=json.loads((ROOT/'config'/'phase4b4_semantic_map.json').read_text(encoding='utf-8'))
    async with Client(mcp) as client:
        result=await audit_live(client,catalog)
    path=ROOT/'reports'/'phase4b42_relationship_audit.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
    print('Saved:',path)
    for rid,r in result['relationships'].items():
        print('RELATIONSHIP',rid, r['status'],'child:',r['child'],'parent:',r['parent'])
    for x in result['grain_investigations']:
        print('GRAIN REVIEW',x['source'],'repeated keys:',x['repeated_key_rows'])
    print('No relationship or measure automatically authorized.')

if __name__=='__main__':
    import asyncio
    asyncio.run(main())
