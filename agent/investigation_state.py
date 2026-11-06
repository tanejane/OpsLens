"""Request-local execution budgets shared by existing governed coordinators."""
import asyncio
import hashlib
import time
from dataclasses import dataclass, field

class BudgetStop(ValueError): pass

@dataclass
class InvestigationState:
    max_steps: int = 4
    max_tools: int = 40
    seconds: float = 120
    clock: object = time.monotonic
    started: float = field(init=False)
    tools: int = 0
    actions: set = field(default_factory=set)
    queries: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)

    def __post_init__(self):
        if type(self.max_steps) is not int or not 1<=self.max_steps<=8 or type(self.max_tools) is not int or not 1<=self.max_tools<=100 or not 0<self.seconds<=180:
            raise ValueError('Invalid investigation budget')
        self.started=self.clock()

    def remaining(self):
        remaining=self.seconds-(self.clock()-self.started)
        if remaining<=0: raise BudgetStop('DEADLINE_REACHED')
        return remaining

    async def read(self,key,operation):
        from copy import deepcopy
        self.remaining()
        digest=hashlib.sha256(key.encode()).hexdigest()
        if digest in self.queries: return deepcopy(self.queries[digest])
        if self.tools>=self.max_tools: raise BudgetStop('TOOL_BUDGET_REACHED')
        self.tools+=1
        result=await asyncio.wait_for(operation(),timeout=self.remaining())
        self.remaining()
        self.queries[digest]=deepcopy(result)
        return result

    def begin(self,action,reason):
        self.remaining()
        if action in self.actions: raise BudgetStop('DUPLICATE_ACTION')
        if len(self.actions)>=self.max_steps: raise BudgetStop('STEP_BUDGET_REACHED')
        self.actions.add(action)
        self.trace.append({'step':len(self.actions),'capability':action,'reason':reason,'decision':'STARTED'})

    def snapshot(self,stop):
        return {'steps_used':len(self.actions),'tools_used':self.tools,'trace':self.trace,
            'stop_reason':stop,'budgets':{'steps':self.max_steps,'tools':self.max_tools,'seconds':self.seconds},'causal_claim':False}
