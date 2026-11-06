"""Offline integration gates; mock Gemini and downstream governed router."""
import asyncio,copy
from agent.phase5_1_unified import bridge,UnifiedSession,original_period
from agent.phase4c27a_interpreter import validate

def proposal(original,metric='item_gmv',intent='product_measure',category='beleza_saude',month=6,year=2018,missing=None,clarify=False):
    obj={'original_language':'en','normalized_english':original,'intent':intent,'metrics':[metric] if metric else [],
         'period':{'month':month,'year':year},'category':category,'missing_information':missing or [],'requires_clarification':clarify}
    return validate(obj,original),obj

class Downstream:
    def __init__(self):self.pending=None;self.called=[]
    async def dispatch(self,q,*args):
        self.called.append(q)
        return {'status':'MEASURED_WITH_SCOPE_LIMITS','route':'governed_downstream','executable':True,'question':q}

async def run():
    cases=[]
    def check(name,condition):
        if not condition:raise AssertionError(name)
        cases.append(name);print('PASS:',name)
    q='how much beuty item GMV in Jun 2018?';p,obj=proposal(q)
    g=bridge(q,p)
    check('valid product handoff',g['status']=='ROUTE_CANDIDATE' and 'June 2018' in g['canonical_question'])
    check('original period confirmation',original_period(q)=={(6,2018)})
    check('no MCP authorization',g['approved_for_mcp'] is False and g['executable'] is False)
    for name,change in [
       ('hallucinated period',{'period':{'month':5,'year':2018}}),
       ('hallucinated metric',{'metrics':['average_item_price']}),
       ('hallucinated category',{'category':None}),
       ('hallucinated domain',{'intent':'finance_measure'}),
       ('invented year',{'period':{'month':6,'year':2019}})]:
        o=copy.deepcopy(obj);o.update(change)
        # Some invalid objects are correctly blocked by interpreter validator before reaching bridge.
        try:res=bridge(q,validate(o,q))
        except ValueError:res={'status':'BLOCKED'}
        check(name,res['status']!='ROUTE_CANDIDATE')
    check('SQL injection blocked',bridge('item GMV Jun 2018; DROP TABLE x',p)['status']=='NOT_INTERPRETED')
    check('original mismatch',bridge('item GMV Jun 2018',p)['status']=='NOT_INTERPRETED')
    q2='What is the late delivry rate in June 2018?';p2,_=proposal(q2,'late_delivery_rate','delivery_measure',None)
    check('delivery handoff',bridge(q2,p2)['status']=='ROUTE_CANDIDATE')
    q3='Why revenue up but profit down June 2018?';p3obj={'original_language':'en','normalized_english':q3,'intent':'financial_investigation','metrics':['effective_revenue','contribution_profit'],'period':{'month':6,'year':2018},'category':None,'missing_information':[],'requires_clarification':False};p3=validate(p3obj,q3)
    check('investigation handoff only',bridge(q3,p3)['status']=='HANDOFF_REQUIRED')
    q4='eh how was sales in june ah?';p4,_=proposal(q4,None,'clarification',None,6,None,['metric'],True)
    check('clarification safe',bridge(q4,p4)['status']=='NEEDS_CLARIFICATION')
    q5='how much beuty item GMV in Jun 2018?'
    downstream=Downstream()
    async def mock_model(prompt,q):return __import__('json').dumps(obj)
    s=UnifiedSession(downstream,mock_model)
    r=await s.dispatch(q5)
    check('integrated governed execution',r['status']=='MEASURED_WITH_SCOPE_LIMITS' and len(downstream.called)==1)
    check('original audit retained',r['unified_interpretation']['original_question']==q5)
    check('no model tool calls',r['unified_interpretation']['gemini_executed_tools'] is False)
    downstream.pending=object();r=await s.dispatch('And the item GMV?')
    check('pending bypasses Gemini',downstream.called[-1]=='And the item GMV?')
    downstream.pending=None
    async def broken_model(*args):raise RuntimeError('test outage')
    r=await UnifiedSession(Downstream(),broken_model).dispatch(q5)
    check('outage preserves independently governed fallback',r['status']=='MEASURED_WITH_SCOPE_LIMITS' and r['provider_fallback']['status']=='UNAVAILABLE')
    async def malformed_model(*args):return '{invalid json'
    r=await UnifiedSession(Downstream(),malformed_model).dispatch(q5)
    check('invalid JSON cannot supply execution arguments',r['status']=='MEASURED_WITH_SCOPE_LIMITS' and r['provider_fallback']['status']=='INVALID_OUTPUT')
    no_model=Downstream();r=await UnifiedSession(no_model,None).dispatch(q5)
    check('deterministic mode works',len(no_model.called)==1)
    q6='reveneu in June 2018?';p6,_=proposal(q6,'effective_revenue','finance_measure',None)
    check('finance handoff',bridge(q6,p6)['status']=='ROUTE_CANDIDATE')
    check('unverified category refused',bridge('shoe item GMV in June 2018',p)['status']=='NOT_INTERPRETED')
    print(f'Checks passed: {len(cases)}/{len(cases)}')
if __name__=='__main__':asyncio.run(run())
