from __future__ import annotations
from typing import Any
from agent.planner_contract import PlannerDecision
from agent.policy_phase3f import DATE_COLUMN_CANDIDATES, MARKETING_COLUMN_CANDIDATES, REFUND_COLUMN_CANDIDATES, _pick

class ProposalRejected(ValueError): pass

def _e(state,eid):
    return next((x for x in state['evidence_ledger'] if x['evidence_id']==eid),None)

def validate_proposal(d: PlannerDecision, state: dict[str,Any]):
    if d.action_type=='stop':
        unresolved=[h for h,v in state['hypotheses'].items() if v['status']=='UNTESTED']
        if unresolved: raise ProposalRejected('Premature stop: '+','.join(unresolved))

def compile_proposal(d: PlannerDecision, state: dict[str,Any]):
    validate_proposal(d,state)
    a,h=d.action_type,d.hypothesis_id
    base={'hypothesis_id':h,'purpose':d.evidence_needed,'planner_rationale':d.rationale,'planner_confidence':d.confidence}
    if a=='stop': return None
    if a=='metric_definition': return {**base,'action_id':'METRIC_DEF','tool_name':'get_metric_definition','arguments':{'metric_name':'contribution_profit'}}
    if a=='schema_discovery':
        if h not in {'H2','H4'}: raise ProposalRejected('Schema discovery not approved for this hypothesis.')
        return {**base,'action_id':f'{h}_SCHEMA','tool_name':'describe_relation','arguments':{'schema':'finance','relation':'daily_pnl'}}
    if a=='knowledge_search':
        if h not in {'H1','H2'}: raise ProposalRejected('Knowledge corroboration only approved for H1/H2 here.')
        q=d.query_hint or ('supplier costs profitability decline' if h=='H1' else 'GrowthMax campaign spend incentives')
        return {**base,'action_id':f'{h}_DOC','tool_name':'search_knowledge','arguments':{'query':q,'top_k':3}}
    if a!='structured_test': raise ProposalRejected('Unsupported action.')
    ev={x['evidence_id'] for x in state['evidence_ledger']}
    if h=='H1' and 'E-OUTCOME' not in ev:
        q="""SELECT DATE_TRUNC('month', business_date)::date AS business_month, SUM(revenue) AS revenue, SUM(contribution_profit) AS contribution_profit, SUM(contribution_profit)/NULLIF(SUM(revenue),0) AS contribution_margin FROM semantic.daily_commerce WHERE business_date >= DATE '2018-02-01' AND business_date < DATE '2018-04-01' GROUP BY 1 ORDER BY 1"""
        return {**base,'hypothesis_id':None,'action_id':'OUTCOME','tool_name':'run_readonly_sql','arguments':{'query':q,'purpose':'Confirm flagship outcome pattern.','expected_grain':'one row per business month','max_rows':12}}
    if h=='H1':
        q="""SELECT DATE_TRUNC('month', NULLIF(order_purchase_timestamp,'')::timestamp)::date AS business_month, SUM(effective_revenue) AS revenue, SUM(effective_cogs) AS cogs FROM semantic.order_economics WHERE NULLIF(order_purchase_timestamp,'')::timestamp >= DATE '2018-02-01' AND NULLIF(order_purchase_timestamp,'')::timestamp < DATE '2018-04-01' GROUP BY 1 ORDER BY 1"""
        return {**base,'action_id':'H1_STRUCTURED','tool_name':'run_readonly_sql','arguments':{'query':q,'purpose':'Compare COGS growth with revenue growth.','expected_grain':'one row per business month','max_rows':12}}
    if h=='H2':
        s=_e(state,'E-H2-SCHEMA')
        if not s: raise ProposalRejected('H2 requires schema discovery.')
        cols=s['value']['columns']; dc=_pick(cols,DATE_COLUMN_CANDIDATES); mc=_pick(cols,MARKETING_COLUMN_CANDIDATES)
        if not dc or not mc: raise ProposalRejected('Approved H2 fields not found.')
        q=f"SELECT DATE_TRUNC('month', NULLIF({dc}::text,'')::timestamp)::date AS business_month, SUM(COALESCE({mc}::double precision,0)) AS marketing_value FROM finance.daily_pnl WHERE NULLIF({dc}::text,'')::timestamp >= DATE '2018-02-01' AND NULLIF({dc}::text,'')::timestamp < DATE '2018-04-01' GROUP BY 1 ORDER BY 1"
        return {**base,'action_id':'H2_STRUCTURED','tool_name':'run_readonly_sql','arguments':{'query':q,'purpose':'Measure marketing cost across deterioration window.','expected_grain':'one row per business month','max_rows':12}}
    if h=='H3':
        return {**base,'action_id':'H3_STRUCTURED','tool_name':'run_readonly_sql','arguments':{'query':'SELECT * FROM semantic.product_mix_effective','purpose':'Check controlled product-mix evidence window.','expected_grain':'controlled product-mix evidence row','max_rows':1000}}
    if h=='H4':
        s=_e(state,'E-H4-SCHEMA')
        if not s: raise ProposalRejected('H4 requires schema discovery.')
        cols=s['value']['columns']; dc=_pick(cols,DATE_COLUMN_CANDIDATES); rc=_pick(cols,REFUND_COLUMN_CANDIDATES)
        if not dc or not rc: raise ProposalRejected('Approved H4 fields not found.')
        q=f"SELECT DATE_TRUNC('month', NULLIF({dc}::text,'')::timestamp)::date AS business_month, SUM(COALESCE({rc}::double precision,0)) AS refund_value FROM finance.daily_pnl WHERE NULLIF({dc}::text,'')::timestamp >= DATE '2018-02-01' AND NULLIF({dc}::text,'')::timestamp < DATE '2018-04-01' GROUP BY 1 ORDER BY 1"
        return {**base,'action_id':'H4_STRUCTURED','tool_name':'run_readonly_sql','arguments':{'query':q,'purpose':'Measure refunds across deterioration window.','expected_grain':'one row per business month','max_rows':12}}
    raise ProposalRejected('Structured test not approved.')
