"""Regression checks for deterministic period-only follow-up rescue; no Gemini/DB required."""
import asyncio
from agent.phase4c1_router import (Conversation, RoutingProposal, route_and_execute,
    is_unambiguous_finance_period_followup)
from agent.phase4b57_nl_dynamic_finance import Context, Intent

class Router:
    def __init__(self, caps=('metric_lookup',), ambiguity='Too brief'):
        self.caps=caps; self.ambiguity=ambiguity
    def propose(self, question, context):
        return RoutingProposal('clarification',self.caps,ambiguity=self.ambiguity)

class Finance:
    def __init__(self, intent): self.intent=intent;self.calls=0
    def interpret(self,q,prior): self.calls+=1; return self.intent

def run():
    ok=0
    def check(name, value):
        nonlocal ok
        assert value,name
        ok+=1;print('PASS:',name)
    prior=Conversation(Context('effective_revenue','2018-04-01','2018-05-01'),'finance_measure')
    check('month followup recognized',is_unambiguous_finance_period_followup('What about March 2018?',prior))
    check('alternative phrase recognized',is_unambiguous_finance_period_followup('How about June 2018?',prior))
    check('yearless month not assumed',not is_unambiguous_finance_period_followup('What about March?',prior))
    check('vague reference not assumed',not is_unambiguous_finance_period_followup('What about that?',prior))
    check('no state not assumed',not is_unambiguous_finance_period_followup('What about March 2018?',Conversation()))
    check('knowledge context not reused',not is_unambiguous_finance_period_followup('What about March 2018?',Conversation(prior.finance,'knowledge')))
    check('why not rescued',not is_unambiguous_finance_period_followup('Why did profit decline in March 2018?',prior))
    check('different metric explicit not rescued',not is_unambiguous_finance_period_followup('What about revenue in March 2018?',prior))
    check('comparison not rescued',not is_unambiguous_finance_period_followup('Compare March and April 2018',prior))
    async def tests():
        calls=0
        async def no_reader(sql,purpose):
            nonlocal calls;calls+=1;raise AssertionError('No database calls expected')
        finance=Finance(Intent(intent='clarify',ambiguity='missing metric'))
        output,next_ctx=await route_and_execute('What about March 2018?',prior,Router(),finance,no_reader)
        check('finance clarification fails closed',output['status']=='ROUTING_DISAGREEMENT' and next_ctx is prior)
        check('finance grounding reached',finance.calls==1)
        check('finance grounding rejection avoids SQL',calls==0)
        finance2=Finance(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'))
        try:await route_and_execute('What about March 2018?',prior,Router(),finance2,no_reader)
        except AssertionError as exc:check('matching grounded request reaches existing guarded executor',str(exc)=='No database calls expected')
        else:raise AssertionError('Reader was not invoked')
        check('no unapproved direct execution',calls==1)
        finance3=Finance(Intent(intent='measure',metric_id='effective_revenue',start_date='2018-03-01',end_date_exclusive='2018-04-01'))
        out,ctx=await route_and_execute('What about that?',prior,Router(),finance3,no_reader)
        check('vague question still clarification',out['status']=='NEEDS_CLARIFICATION' and ctx is prior)
        check('no finance call on vague question',finance3.calls==0)
        out,ctx=await route_and_execute('What about March 2018?',prior,Router(('diagnostic_investigation',),'vague'),finance3,no_reader)
        check('other capabilities not rescued',out['route']=='clarification' and ctx is prior)
    asyncio.run(tests());print(f'Checks passed: {ok}/{ok}')
if __name__=='__main__':run()
