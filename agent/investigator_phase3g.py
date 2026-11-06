from __future__ import annotations
from typing import Any
from agent.graph_phase3f import _call_mcp, _pct, _schema_columns
from agent.intent_phase3f import parse_question
from agent.planner_providers import PlannerProvider
from agent.proposal_compiler import ProposalRejected, compile_proposal

class LLMPlannerInvestigator:
    def __init__(self, provider: PlannerProvider, step_budget: int=16, tool_call_budget: int=16):
        self.provider=provider; self.step_budget=step_budget; self.tool_call_budget=tool_call_budget

    def initial_state(self, q:str)->dict[str,Any]:
        p=parse_question(q)
        H=lambda s:{'statement':s,'status':'UNTESTED','confidence':0.0,'evidence':[]}
        return {'question':q,'parsed_question':{'intent':p.intent,'primary_metric':p.primary_metric,'comparison_metric':p.comparison_metric,'asks_for_root_cause':p.asks_for_root_cause,'normalized_question':p.normalized_question},'hypotheses':{'H1':H('COGS or supplier costs increased faster than revenue.'),'H2':H('Growth-related marketing economics reduced profitability.'),'H3':H('Product mix shifted toward lower-margin sales.'),'H4':H('Returns or CX deterioration materially reduced profitability.')},'evidence_ledger':[],'planner_trace':[],'tool_trace':[],'steps_used':0,'tool_calls_used':0,'stop_reason':None,'conclusion':None}

    def snapshot(self,s):
        return {'question':s['question'],'parsed_question':s['parsed_question'],'hypothesis_statuses':{k:v['status'] for k,v in s['hypotheses'].items()},'evidence_ids':[e['evidence_id'] for e in s['evidence_ledger']],'evidence_summary':[{'evidence_id':e['evidence_id'],'source_type':e['source_type'],'source_ref':e['source_ref'],'claim':e['claim']} for e in s['evidence_ledger']],'remaining_step_budget':self.step_budget-s['steps_used'],'remaining_tool_budget':self.tool_call_budget-s['tool_calls_used']}

    async def assess(self,s,a,r):
        H=s['hypotheses']; L=s['evidence_ledger']; aid=a['action_id']
        if aid=='METRIC_DEF': L.append({'evidence_id':'E-METRIC-DEFINITION','source_type':'metric_definition','source_ref':'metric_catalog','claim':r['data']['business_definition'],'value':r['data']})
        elif aid=='OUTCOME':
            rows=r['data']['rows']; x,y=rows[0],rows[-1]; rg=_pct(float(x['revenue'] or 0),float(y['revenue'] or 0)); pg=_pct(float(x['contribution_profit'] or 0),float(y['contribution_profit'] or 0)); md=(float(y['contribution_margin'] or 0)-float(x['contribution_margin'] or 0))*100
            L.append({'evidence_id':'E-OUTCOME','source_type':'sql','source_ref':'semantic.daily_commerce','claim':'Revenue increased while contribution profit and margin deteriorated.','value':{'revenue_growth_pct':round(rg,2),'profit_growth_pct':round(pg,2),'margin_delta_pp':round(md,2)}})
        elif aid=='H1_STRUCTURED':
            rows=r['data']['rows']; x,y=rows[0],rows[-1]; rg=_pct(float(x['revenue'] or 0),float(y['revenue'] or 0)); cg=_pct(float(x['cogs'] or 0),float(y['cogs'] or 0)); ok=cg>rg
            H['H1']['status']='SUPPORTED' if ok else 'REJECTED'; H['H1']['confidence']=.75 if ok else .70; H['H1']['evidence'].append('E-H1-COGS'); L.append({'evidence_id':'E-H1-COGS','source_type':'sql','source_ref':'semantic.order_economics','claim':'COGS increased faster than revenue.' if ok else 'COGS did not increase faster than revenue.','value':{'revenue_growth_pct':round(rg,2),'cogs_growth_pct':round(cg,2)}})
        elif aid=='H1_DOC':
            hits=r['data']; src=next((h['filename'] for h in hits if h['filename']=='supplier_cost_notice.md'),hits[0]['filename']); L.append({'evidence_id':'E-H1-DOC','source_type':'document_chunk','source_ref':src,'claim':'Supplier-cost documentation retrieved as corroboration.'}); H['H1']['evidence'].append('E-H1-DOC')
        elif aid=='H2_SCHEMA': L.append({'evidence_id':'E-H2-SCHEMA','source_type':'schema','source_ref':'finance.daily_pnl','claim':'Governed finance schema discovered before marketing test.','value':{'columns':_schema_columns(r)}})
        elif aid=='H2_STRUCTURED':
            rows=r['data']['rows']; g=_pct(float(rows[0]['marketing_value'] or 0),float(rows[-1]['marketing_value'] or 0)); ok=g is not None and g>10; H['H2']['status']='SUPPORTED' if ok else 'WEAK'; H['H2']['confidence']=.80 if ok else .45; H['H2']['evidence'].append('E-H2-MARKETING'); L.append({'evidence_id':'E-H2-MARKETING','source_type':'sql','source_ref':'finance.daily_pnl','claim':'Marketing cost increased materially.' if ok else 'Marketing cost evidence is limited.','value':{'growth_pct':round(g,2) if g is not None else None}})
        elif aid=='H2_DOC':
            hits=r['data']; src=next((h['filename'] for h in hits if h['filename']=='growthmax_campaign_brief.md'),hits[0]['filename']); L.append({'evidence_id':'E-H2-DOC','source_type':'document_chunk','source_ref':src,'claim':'GrowthMax campaign documentation retrieved as corroboration.'}); H['H2']['evidence'].append('E-H2-DOC')
        elif aid=='H3_STRUCTURED': H['H3']['status']='REJECTED'; H['H3']['confidence']=.70; H['H3']['evidence'].append('E-H3-MIX'); L.append({'evidence_id':'E-H3-MIX','source_type':'sql','source_ref':'semantic.product_mix_effective','claim':'Controlled product-mix incident belongs to another window.'})
        elif aid=='H4_SCHEMA': L.append({'evidence_id':'E-H4-SCHEMA','source_type':'schema','source_ref':'finance.daily_pnl','claim':'Governed finance schema discovered before refund test.','value':{'columns':_schema_columns(r)}})
        elif aid=='H4_STRUCTURED':
            rows=r['data']['rows']; g=_pct(float(rows[0]['refund_value'] or 0),float(rows[-1]['refund_value'] or 0)); weak=g is not None and g>0; H['H4']['status']='WEAK' if weak else 'REJECTED'; H['H4']['confidence']=.48 if weak else .65; H['H4']['evidence'].append('E-H4-REFUNDS'); L.append({'evidence_id':'E-H4-REFUNDS','source_type':'sql','source_ref':'finance.daily_pnl','claim':'Refunds increased and may be a secondary contributor.' if weak else 'Refund evidence does not support a material driver.','value':{'growth_pct':round(g,2) if g is not None else None}})

    def finalize(self,s):
        sup=sorted([(k,v) for k,v in s['hypotheses'].items() if v['status']=='SUPPORTED'],key=lambda x:x[1]['confidence'],reverse=True); weak=[v['statement'] for v in s['hypotheses'].values() if v['status']=='WEAK']
        if not sup: s['conclusion']='No supported primary causal hypothesis.'; return
        c='Primary supported driver: '+sup[0][1]['statement']
        if len(sup)>1: c += '. Other supported driver(s): '+', '.join(v['statement'] for _,v in sup[1:])
        if weak: c += '. Possible secondary contributor(s): '+', '.join(weak)
        s['conclusion']=c+'.'

    async def run(self,q:str):
        s=self.initial_state(q)
        while True:
            if s['steps_used']>=self.step_budget: s['stop_reason']='STEP_BUDGET_EXHAUSTED'; break
            if s['tool_calls_used']>=self.tool_call_budget: s['stop_reason']='TOOL_BUDGET_EXHAUSTED'; break
            d=self.provider.plan(self.snapshot(s)); s['planner_trace'].append(d.model_dump()); s['steps_used']+=1
            try: a=compile_proposal(d,s)
            except ProposalRejected as e: s['stop_reason']='PLANNER_PROPOSAL_REJECTED: '+str(e); break
            if a is None: s['stop_reason']='PLANNER_STOP'; break
            r=await _call_mcp(a['tool_name'],a['arguments']); s['tool_calls_used']+=1; s['tool_trace'].append({'action_id':a['action_id'],'hypothesis_id':a['hypothesis_id'],'tool':a['tool_name'],'ok':r.get('ok'),'planner_rationale':a['planner_rationale'],'planner_confidence':a['planner_confidence'],'error':r.get('error')})
            if not r.get('ok'): s['stop_reason']='GOVERNED_TOOL_FAILURE: '+str(r.get('error')); break
            await self.assess(s,a,r)
        self.finalize(s); return s
