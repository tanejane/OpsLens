"""Deterministic tests; no live DB, LLM or MCP needed."""
import asyncio
from agent.phase4c25_clarification import ClarificationSession

class Stub:
    def __init__(self):self.calls=[]
    async def dispatch(self,q,*args):
        self.calls.append(q)
        return {'route':'delegated','question':q,'executable':True}

async def main():
    n=0
    async def check(name,fn):
        nonlocal n
        await fn()
        n+=1;print('PASS:',name)
    async def tests():
        stub=Stub();s=ClarificationSession(stub)
        async def p(q):return await s.dispatch(q)
        x=await p('How were sales in June 2018?')
        assert x['status']=='NEEDS_CLARIFICATION' and x['retained']['period']=='June 2018' and not stub.calls
        x=await p('item GMV');assert x['status']=='NEEDS_CLARIFICATION' and x['retained']['metric']=='item_gmv' and not stub.calls
        x=await p('health and beauty');assert x['executable'] and stub.calls[-1]=='What was the item GMV for health and beauty in June 2018?'
        x=await p('Show me sales for May 2018');assert x['retained']['period']=='May 2018'
        x=await p('units');assert x['retained']['metric']=='units_sold'
        x=await p('beleza_saude');assert x['question']=='How many health and beauty products were sold in May 2018?'
        x=await p('sales');assert not x['executable']
        x=await p('random');assert not x['executable'] and len(stub.calls)==2
        x=await p('revenue');assert x['status']=='NEEDS_CLARIFICATION' and x['retained']['metric']=='financial_revenue'
        x=await p('June 2018');assert x['route']=='delegated' and x['question']=='What was revenue in June 2018?'
        x=await p('cancel');assert x['status']=='CANCELLED' and s.pending is None
        x=await p('How were sales in June 2018?');assert not x['executable']
        x=await p('What is the late delivery rate in June 2018?');assert x['route']=='delegated' and s.pending is None
        x=await p('revenue');assert x['question']=='revenue' # no pending context
        x=await p('sales');assert x['status']=='NEEDS_CLARIFICATION'
        x=await p('DROP; TABLE');assert not x['executable'] and s.pending is None
        x=await p('How were sales in June 2018?');assert not x['executable']
        x=await p('profit comparison for May 2018');assert x['route']=='delegated'
        x=await p('sales');assert not x['executable']
        x=await p('shoes');assert not x['executable']
        assert 'shoes' not in stub.calls
    await check('multi-turn context and safety',tests)
    for phrase in ['How were sales in June 2018?','Show me sales for June 2018','Sales?','How is sales doing?']:
        async def check_phrase(q=phrase):
            s=ClarificationSession(Stub());r=await s.dispatch(q)
            assert r['status']=='NEEDS_CLARIFICATION' and r['executable'] is False
        await check('clarifies '+phrase,check_phrase)
    for phrase in ['health and beauty','health & beauty','health_beauty','beleza_saude']:
        async def check_cat(q=phrase):
            stub=Stub();s=ClarificationSession(stub)
            await s.dispatch('sales for June 2018');await s.dispatch('item GMV')
            r=await s.dispatch(q);assert r['executable'] and len(stub.calls)==1
        await check('approved category '+phrase,check_cat)
    for phrase in ['shoe products','a random category','; DROP','UNKNOWN']:
        async def check_bad(q=phrase):
            stub=Stub();s=ClarificationSession(stub)
            await s.dispatch('sales for June 2018');await s.dispatch('units')
            r=await s.dispatch(q);assert not r['executable'] and not stub.calls
        await check('blocks unsupported '+phrase,check_bad)
    print(f'Checks passed: {n}/{n}')
if __name__=='__main__':asyncio.run(main())
