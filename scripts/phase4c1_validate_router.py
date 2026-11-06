"""Offline safety and integration tests: no Gemini key or database required."""
import asyncio
from agent.phase4c1_router import RoutingProposal,Conversation,validate_route,route_and_execute,RoutingRejected
from agent.phase4b57_nl_dynamic_finance import Context,Intent

def run():
    tests=[]
    def check(label,condition):
        assert condition,label
        tests.append(label);print('PASS:',label)
    def r(*c,ambiguity=None):return validate_route(RoutingProposal('analyze',tuple(c),ambiguity=ambiguity))
    check('metric lookup routed',r('metric_lookup').route=='finance_measure')
    check('comparison routed',r('metric_lookup','period_comparison').route=='finance_compare')
    check('root-cause wins over comparison',r('period_comparison','diagnostic_investigation').route=='investigation')
    check('root-cause is not executed',not r('metric_lookup','diagnostic_investigation').executable)
    check('ranking handoff',r('ranking').status=='HANDOFF_REQUIRED')
    check('trend handoff',r('time_trend').route=='graph_analytics')
    check('simulation blocked',r('simulation').status=='NOT_IMPLEMENTED')
    check('unknown capability blocked',r('invent_sql').route=='unsupported')
    check('knowledge handoff',r('knowledge_retrieval').route=='knowledge')
    check('mixed knowledge staged',r('knowledge_retrieval','metric_lookup').route=='clarification')
    check('ambiguous request clarified',r('metric_lookup',ambiguity='which month?').route=='clarification')
    check('duplicate capabilities deduped',r('metric_lookup','metric_lookup').capabilities==('metric_lookup',))
    try:validate_route(RoutingProposal('foo',('metric_lookup',),confidence=1.1))
    except RoutingRejected:check('invalid confidence blocked',True)
    else:raise AssertionError('confidence')
    class Router:
        def __init__(self,proposal):self.proposal=proposal
        def propose(self,q,context):return self.proposal
    class Finance:
        def __init__(self,intent):self.intent=intent
        def interpret(self,q,prior):return self.intent
    async def scenarios():
        prior=Conversation(Context('effective_revenue','2018-04-01','2018-05-01'),'finance_measure')
        count=0
        async def reader(sql,purpose):
            nonlocal count
            count+=1
            raise AssertionError('Must not execute')
        for caps in [('diagnostic_investigation',),('ranking',),('simulation',),('knowledge_retrieval',)]:
            response,ctx=await route_and_execute('question',prior,Router(RoutingProposal('intent',caps)),Finance(None),reader)
            check('safe no-op '+caps[0],ctx is prior and 'evidence' not in response)
        check('no db calls on unsupported requests',count==0)
        intent=Intent(intent='investigate',metric_id='effective_revenue')
        response,ctx=await route_and_execute('why',prior,Router(RoutingProposal('x',('metric_lookup',))),Finance(intent),reader)
        check('finance interpretation disagreement blocks',response['status']=='ROUTING_DISAGREEMENT' and ctx is prior)
        check('no SQL on disagreement',count==0)
    asyncio.run(scenarios())
    print(f'Checks passed: {len(tests)}/{len(tests)}')
if __name__=='__main__':run()
