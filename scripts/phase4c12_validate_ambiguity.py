"""Phase 4C.1.2: ambiguity, clarification, disagreement and safety regression."""
import asyncio
from agent.phase4c1_router import (Conversation, RoutingProposal, route_and_execute,
    needs_reference_clarification, clarification_envelope)
from agent.phase4b57_nl_dynamic_finance import Context, Intent

class FakeRouter:
    def __init__(self, proposal): self.proposal=proposal;self.calls=0
    def propose(self, question, context): self.calls+=1;return self.proposal
class FakeFinance:
    def __init__(self, intent): self.intent=intent;self.calls=0
    def interpret(self, question, context):self.calls+=1;return self.intent

def run():
    n=0
    def ck(name,condition):
        nonlocal n
        assert condition,name
        n+=1;print('PASS:',name)
    ctx=Conversation(Context('effective_revenue','2018-03-01','2018-04-01'),'finance_measure')
    for text in ['What about that?','How about it?','What about this','And then?','And that one?']:
        ck('vague detected '+text,needs_reference_clarification(text))
    for text in ['What about March 2018?','What about contribution margin?','Compare March and April 2018','Why was revenue down?','What about that in June 2018?']:
        ck('substantive not intercepted '+text,not needs_reference_clarification(text))
    ck('clarification contextualized', 'effective_revenue' in clarification_envelope('What about that?',ctx)['reason'])
    ck('no history safe',clarification_envelope('What about that?',Conversation())['status']=='NEEDS_CLARIFICATION')
    async def tests():
        calls=0
        async def reader(sql,purpose):
            nonlocal calls
            calls+=1
            raise AssertionError('unexpected query')
        route=FakeRouter(RoutingProposal('lookup',('metric_lookup',)))
        finance=FakeFinance(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'))
        result,new=await route_and_execute('What about that?',ctx,route,finance,reader)
        ck('vague is clarification',result['status']=='NEEDS_CLARIFICATION')
        ck('no router call for vague',route.calls==0)
        ck('no finance call for vague',finance.calls==0)
        ck('no SQL on vague',calls==0)
        ck('state identity preserved on vague',new is ctx)
        result,new=await route_and_execute('How about it?',Conversation(),route,finance,reader)
        ck('vague without context clarified',result['status']=='NEEDS_CLARIFICATION' and new==Conversation())
        bad=FakeRouter(RoutingProposal('comparison',('period_comparison',)))
        conflicting=FakeFinance(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'))
        result,new=await route_and_execute('Compare April and March revenue',ctx,bad,conflicting,reader)
        ck('genuine disagreement still blocked',result['status']=='ROUTING_DISAGREEMENT')
        ck('disagreement no SQL',calls==0)
        ck('disagreement state preserved',new is ctx)
        ck('interpreter was actually consulted',conflicting.calls==1)
        vague_router=FakeRouter(RoutingProposal('clarification',('metric_lookup',),ambiguity='too short'))
        no_finance=FakeFinance(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'))
        try:
            await route_and_execute('What about March 2018?',ctx,vague_router,no_finance,reader)
        except AssertionError as exc:
            ck('protected executor reached for real date followup',str(exc)=='unexpected query')
        else:
            raise AssertionError('expected protected executor invocation')
        ck('guarded finance invoked',calls==1 and no_finance.calls==1)
    asyncio.run(tests())
    print(f'Checks passed: {n}/{n}')
if __name__=='__main__':run()
