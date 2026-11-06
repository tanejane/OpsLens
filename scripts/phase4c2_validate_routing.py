"""Offline end-to-end routing tests without LLM API, Docker or database."""
import asyncio
from dataclasses import dataclass
from agent.phase4c2_graph_routing import (UnifiedContext, dispatch, validate_graph_response, GraphRouteRejected)
from agent.phase4c1_router import RoutingProposal,Conversation
from agent.phase4b44_context_grounding import Interpretation
from agent.phase4b43_graph_planner import AnalysisRequest

class Router:
    def __init__(self,cap):self.cap=cap
    def propose(self,q,state):return RoutingProposal('test',(self.cap,))
class Interpreter:
    def __init__(self):self.previous=[]
    def interpret(self,q,map_obj,prior):
        self.previous.append(prior)
        if 'July' in q:
            return Interpretation(intent='ranking',dimensions=[],start_date='2018-07-01',end_date_exclusive='2018-08-01',inherit=['metric','dimensions','order','limit'])
        return Interpretation(intent='ranking',metric_id='unique_orders',dimensions=['seller_id'],start_date='2018-06-01',end_date_exclusive='2018-07-01',order='desc',limit=5)
class FakeMap:
    metrics={'unique_orders':{'source':'commerce.orders','allowed_dimensions':['seller_id']}}
    dimensions={'seller_id':{'source':'commerce.order_items'}}
    sources={'commerce.orders':{'scope':'marketplace'},'commerce.order_items':{'scope':'marketplace'}}
class Planner:
    map=FakeMap()
    def compile(self,req):
        assert req.metric=='unique_orders' and req.dimensions==('seller_id',)
        return {'sql':'SELECT safe SQL','sources':['commerce.orders','commerce.order_items'],
                'relationships':['orders_to_items'],'safety':'distinct orders protected'}

async def main():
    checks=[]
    def ok(cond,label):
        assert cond,label
        checks.append(label);print('PASS:',label)
    graph=Interpreter();planner=Planner();calls=[]
    async def reader(sql,req,plan):
        calls.append(req)
        return {'ok':True,'data':{'rows':[{'seller_id':'sellerA','metric_value':160}]}}
    async def forbidden(*args):raise AssertionError('Finance reader must not run')
    state=UnifiedContext()
    args=(None,forbidden,graph,planner,reader)
    out,state=await dispatch('Which five sellers received the most orders in June 2018?',state,Router('ranking'),*args)
    ok(out['route']=='graph_analytics','ranking dispatched to graph')
    ok(out['evidence']['metric_id']=='unique_orders','approved metric carried')
    ok(out['evidence']['source_relations']==['commerce.orders','commerce.order_items'],'source provenance preserved')
    ok(state.graph_request is not None,'successful graph context saved')
    ok(state.conversation.finance is None,'finance context isolated')
    prior=state
    out,state=await dispatch('What about July 2018?',state,Router('metric_lookup'),*args)
    ok(out['route']=='graph_analytics','month followup resumes graph domain')
    ok(state.graph_request.start_date=='2018-07-01','updated graph period')
    ok(graph.previous[-1]==prior.graph_request,'prior graph request inherited')
    ok(len(calls)==2,'two successful graph executions')
    out,state2=await dispatch('What about that?',state,Router('ranking'),*args)
    ok(out['status']=='NEEDS_CLARIFICATION','vague reference clarified')
    ok(state2==state,'clarification does not mutate context')
    ok(len(calls)==2,'clarification did not hit database')
    async def empty(sql,req,plan):return {'ok':True,'data':{'rows':[]}}
    try:await dispatch('Which five sellers received the most orders in June 2018?',state,Router('ranking'),None,forbidden,graph,planner,empty)
    except GraphRouteRejected:ok(True,'empty rows fail closed')
    else:raise AssertionError('empty accepted')
    ok(len(calls)==2,'failed graph execution does not use successful reader')
    for response,label in [({'ok':False,'error':'denied'},'MCP rejection blocked'),
                           ({'ok':True,'data':{'rows':[{'metric_value':None,'seller_id':'s'}]}},'null metric blocked'),
                           ({'ok':True,'data':{'rows':[{'metric_value':1}]}},'missing dimension blocked'),
                           ({'ok':True,'data':{'rows':[{'metric_value':1,'seller_id':'s'}]*6}},'row bound enforced')]:
        try:validate_graph_response(response,{'sources':[],'relationships':[],'safety':''},
                AnalysisRequest('unique_orders',('seller_id',),'2018-06-01','2018-07-01','desc',5))
        except GraphRouteRejected:ok(True,label)
        else:raise AssertionError(label)
    out,next_state=await dispatch('Why did profit decrease?',state,Router('diagnostic_investigation'),*args)
    ok(out['status']=='INVESTIGATION_NOT_YET_CONNECTED','investigation remains handoff')
    ok(next_state==state,'investigation preserves prior graph context')
    out,next_state=await dispatch('What if marketing spend doubled?',state,Router('simulation'),*args)
    ok(out['status']=='NOT_IMPLEMENTED','simulation stays blocked')
    ok(next_state==state,'simulation preserves context')
    print(f'Checks passed: {len(checks)}/{len(checks)}')
if __name__=='__main__':asyncio.run(main())
