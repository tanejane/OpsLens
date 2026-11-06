"""Standalone deterministic regression; no database, LLM or MCP access."""
import asyncio
from agent.phase4c26_recovery import RecoverySession, period_choice
class Stub:
 def __init__(self):self.calls=[]
 async def dispatch(self,q,*args):
  self.calls.append(q);return {'route':'delegated','question':q,'executable':True}
async def main():
 checks=0
 async def check(name,fn):
  nonlocal checks
  await fn();checks+=1;print('PASS:',name)
 async def scenario(steps,last=None,expected_calls=None):
  stub=Stub();s=RecoverySession(stub);res=None
  for q in steps:res=await s.dispatch(q)
  if last is not None:assert res['status']==last,res
  if expected_calls is not None:assert stub.calls==expected_calls,stub.calls
  return s,res
 for q,period in [('June 2018','June 2018'),('六月2018','June 2018'),('六月 2018','June 2018'),('2018年六月','June 2018'),('六月2018','June 2018'),('2018年十二月','December 2018'),('2018年五月2017',None),('May 2018 and June 2018',None),('2018/06/12',None)]:
  async def f(q=q,period=period):
   # Chinese month-year is supported only in explicit syntax; unqualified text rejected.
   val=period_choice(q)
   assert val==period,(q,val,period)
  await check('period '+q,f)
 async def f1():
  s,r=await scenario(['sales for June 2018','no, I meant May 2018','item GMV','health and beauty'],expected_calls=['What was the item GMV for health and beauty in May 2018?'])
 await check('correct period before metric',f1)
 async def f2():
  s,r=await scenario(['sales for June 2018','units','make that May 2018','beleza_saude'],expected_calls=['How many health and beauty products were sold in May 2018?'])
 await check('correct period after metric',f2)
 async def f3():
  s,r=await scenario(['sales','financial revenue','2018年六月'],expected_calls=['What was revenue in June 2018?'])
 await check('financial date reply Chinese',f3)
 async def f4():
  s,r=await scenario(['sales for June 2018','units','no, item GMV','health and beauty'],expected_calls=['What was the item GMV for health and beauty in June 2018?'])
 await check('correct metric',f4)
 async def f5():
  s,r=await scenario(['sales for June 2018','item GMV','not approved category'],last='NEEDS_CLARIFICATION',expected_calls=[])
 await check('unknown category fail closed',f5)
 async def f6():
  s,r=await scenario(['sales for June 2018','no, shoes'],last='NEEDS_CLARIFICATION',expected_calls=[])
 await check('unsupported correction fail closed',f6)
 async def f7():
  s,r=await scenario(['sales for June 2018','no, May 2018; DROP TABLE x'],last='NEEDS_CLARIFICATION',expected_calls=[])
  assert s.pending is None
 await check('SQL syntax rejected',f7)
 async def f8():
  s,r=await scenario(['sales for June 2018','What is the late delivery rate in June 2018?'],expected_calls=['What is the late delivery rate in June 2018?'])
  assert s.pending is None
 await check('topic switch clears pending',f8)
 async def f9():
  s,r=await scenario(['sales for June 2018','cancel'],last='CANCELLED',expected_calls=[])
  assert s.pending is None
 await check('cancel clears pending',f9)
 async def f10():
  s,r=await scenario(['sales for June 2018','no, I meant a different category'],last='NEEDS_CLARIFICATION',expected_calls=[])
 await check('ambiguous correction blocked',f10)
 async def f11():
  s,r=await scenario(['sales for June 2018','rather May 2018','units','health and beauty'],expected_calls=['How many health and beauty products were sold in May 2018?'])
 await check('rather prefix',f11)
 print(f'Checks passed: {checks}/{checks}')
if __name__=='__main__':asyncio.run(main())
