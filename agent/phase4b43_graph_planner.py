"""OpsLens 4B.4.3: graph-based, metric-grain-aware read-only query compiler.

No question-specific SQL templates. Only composable semantic primitives and audited edges.
Structural FK checks alone are never interpreted as measure-safe approval.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json,re
from agent.phase4b4_semantic_map import SemanticMap

_IDENT=re.compile(r'^[a-z_][a-z_0-9]*$')
class PlanningRejected(ValueError): pass

def ident(s):
    if not isinstance(s,str) or not _IDENT.fullmatch(s):raise PlanningRejected('Unsafe SQL identifier')
    return '"'+s+'"'
def table(s):
    a=s.split('.')
    if len(a)!=2:raise PlanningRejected('Invalid relation name')
    return '.'.join(map(ident,a))
def date_expr(alias,column):
    col=f'{alias}.{ident(column)}'
    return (f'(CASE WHEN pg_input_is_valid(NULLIF(BTRIM({col}::text), \'\'), '
            f"'timestamp without time zone') THEN NULLIF(BTRIM({col}::text), '')::timestamp ELSE NULL END)")

def require_date_pair(start,end):
    if not start or not end:raise PlanningRejected('Explicit start and end dates required (no implicit all-time scope)')
    try: lo,hi=date.fromisoformat(start),date.fromisoformat(end)
    except (ValueError,TypeError):raise PlanningRejected('Invalid ISO date') from None
    if lo>=hi:raise PlanningRejected('Invalid date interval')
    return lo,hi

@dataclass(frozen=True)
class AnalysisRequest:
    metric:str
    dimensions:tuple[str,...]=()
    start_date:str|None=None
    end_date_exclusive:str|None=None
    order:str='desc'
    limit:int=10

class GraphPlanner:
    def __init__(self,audit_path, map_path=None):
        self.map=SemanticMap(map_path) if map_path else SemanticMap()
        self.audit=json.loads(Path(audit_path).read_text(encoding='utf-8'))
        if not isinstance(self.audit.get('relationships'),dict) or not isinstance(self.audit.get('sources'),dict):
            raise PlanningRejected('Missing live audit sections')

    def _source(self,s,required):
        report=self.audit['sources'].get(s)
        if not report or not report.get('columns_verified') or set(required)-set(report.get('live_columns',[])):
            raise PlanningRejected('Missing verified live source columns: '+s)
        if report.get('checks',{}).get('grain',{}).get('status')!='VERIFIED':
            raise PlanningRejected('Unverified source grain: '+s)
        return report

    def _edge(self,edge):
        a=self.audit['relationships'].get(edge['id'],{})
        if a.get('status')!='STRUCTURALLY_VERIFIED':raise PlanningRejected('Relationship not structurally verified: '+edge['id'])
        if a.get('execution_approved') is True:
            # Never rely on blanket approval from a report.
            pass
        if a.get('parent') not in (edge['left'],edge['right']) or a.get('child') not in (edge['left'],edge['right']):
            raise PlanningRejected('Relationship audit endpoints inconsistent: '+edge['id'])
        if a.get('foreign_key_audit',{}).get('orphan_fk_rows')!=0:
            raise PlanningRejected('FK not fully verified: '+edge['id'])
        if a.get('parent_key_audit',{}).get('repeated_key_rows')!=0:
            raise PlanningRejected('Parent uniqueness not verified: '+edge['id'])
        return a

    def compile(self,req:AnalysisRequest):
        lo,hi=require_date_pair(req.start_date,req.end_date_exclusive)
        if req.order not in ('asc','desc'):raise PlanningRejected('Invalid sort direction')
        if not isinstance(req.limit,int) or not 1<=req.limit<=100:raise PlanningRejected('Limit must be 1..100')
        if len(set(req.dimensions))!=len(req.dimensions) or len(req.dimensions)>2:raise PlanningRejected('Invalid dimensions')
        metric=self.map.metrics.get(req.metric)
        if not metric:raise PlanningRejected('Unknown metric; no approximation')
        source=metric['source']; src=self.map.sources[source]
        if any(d not in metric['allowed_dimensions'] for d in req.dimensions):
            # unique_orders by category is structurally possible but requires explicit catalog permission.
            raise PlanningRejected('Metric/dimension combination not allowed by semantic contract')
        if src.get('scope')=='incident_specific':
            raise PlanningRejected('Incident-specific measures disabled pending validated source grain')
        coverage=src.get('coverage')
        if coverage and (lo<date.fromisoformat(coverage['start']) or hi>date.fromisoformat(coverage['end_exclusive'])):
            raise PlanningRejected('Period outside source coverage')
        aliases={source:'t0'}; joins=[]; edges_used=[]
        required={source:set(metric.get('grain',[]))}
        for d in req.dimensions:
            dim=self.map.dimensions.get(d)
            if not dim:raise PlanningRejected('Unknown dimension')
            target=dim['source']
            path=self.map.path(source,target)
            # find connected edges in sequence using existing aliases; graph path may share prefixes.
            for e in path:
                self._edge(e)
                a,b=e['left'],e['right']
                if a in aliases and b not in aliases:
                    anchor,nextnode,ak,nk=a,b,e['left_key'],e['right_key']
                elif b in aliases and a not in aliases:
                    anchor,nextnode,ak,nk=b,a,e['right_key'],e['left_key']
                elif a in aliases and b in aliases:
                    continue
                else:raise PlanningRejected('Noncontiguous relationship traversal')
                alias='t'+str(len(aliases));aliases[nextnode]=alias
                required.setdefault(anchor,set()).add(ak)
                required.setdefault(nextnode,set()).add(nk)
                joins.append(f'JOIN {table(nextnode)} {alias} ON {aliases[anchor]}.{ident(ak)} = {alias}.{ident(nk)}')
                edges_used.append(e['id'])
            required.setdefault(target,set()).add(dim['column'])
        # Date is evaluated at the metric source grain or via an explicitly equivalent order source.
        date_source=source
        if not src.get('date_column'):
            raise PlanningRejected('Metric source has no approved date column')
        required[source].add(src['date_column'])
        for name,cols in required.items():self._source(name,cols)
        # Measure safety: DISTINCT order IDs can traverse fanout; daily ratios cannot.
        kind=metric['expression_kind']
        alias=aliases[source]
        if kind=='distinct_count':
            if metric['column']!='order_id' or source!='commerce.orders':
                raise PlanningRejected('Distinct-count contract not yet proven for this grain')
            expression=f'COUNT(DISTINCT {alias}.{ident(metric["column"])})'
            safety='distinct order IDs protect against item-level join fanout'
        elif kind=='ratio_of_sums':
            if joins:raise PlanningRejected('Ratio measure cannot cross a join without preaggregation/allocation')
            if source!='semantic.daily_commerce':raise PlanningRejected('Unapproved ratio source')
            numerator=metric['numerator'];denominator=metric['denominator']
            if denominator!='revenue' or numerator not in ('revenue_minus_cogs','contribution_profit'):
                raise PlanningRejected('Unapproved numerator or denominator')
            required_columns=['revenue','cogs'] if numerator=='revenue_minus_cogs' else ['revenue','contribution_profit']
            self._source(source,required_columns)
            num=(f'SUM({alias}."revenue") - SUM({alias}."cogs")' if numerator=='revenue_minus_cogs' else f'SUM({alias}."contribution_profit")')
            expression=f'100.0 * ({num}) / NULLIF(SUM({alias}."revenue"),0)'
            safety='ratio of aggregate sums at daily-commerce grain'
        else:raise PlanningRejected('Unsupported metric expression kind')
        ds=date_expr(alias,src['date_column'])
        selections=[]
        for d in req.dimensions:
            dim=self.map.dimensions[d]
            selections.append((f'{aliases[dim["source"]]}.{ident(dim["column"])}',d))
        selects=[f'{expr} AS {ident(name)}' for expr,name in selections]+[expression+' AS metric_value']
        where=f'{ds} >= DATE \'{lo.isoformat()}\' AND {ds} < DATE \'{hi.isoformat()}\''
        groups=' GROUP BY '+', '.join(str(i+1) for i in range(len(selections))) if selections else ''
        ordering=(' ORDER BY metric_value '+req.order.upper()+' NULLS LAST'+(', '+', '.join(ident(d)+' ASC' for d in req.dimensions) if req.dimensions else '') if selections else '')
        sql=(f'SELECT {", ".join(selects)} FROM {table(source)} {alias} '
             +(' '.join(joins)+' ' if joins else '')+f'WHERE {where}'+groups+ordering+f' LIMIT {req.limit}')
        return {'sql':sql,'metric':req.metric,'dimensions':list(req.dimensions),'sources':list(aliases),
                'relationships':edges_used,'safety':safety,'coverage':'RANGE_NOT_YET_PROBED',
                'notice':'Structural audit is not measure approval; this compiler permits only its explicitly justified measure-safe operations. Live period availability remains unverified until execution.'}
