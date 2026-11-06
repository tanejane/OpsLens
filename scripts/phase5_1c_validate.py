"""Dependency-free focused regression for delivery comparison routing."""
import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Import only the router's pure module with stub dependencies.  No DB or LLM.
def stub(name, **items):
    mod=types.ModuleType(name)
    mod.__dict__.update(items)
    sys.modules[name]=mod

class FakeSession:
    def __init__(self,*args,**kw):pass
class Context:
    def __init__(self,*args):pass
stub('agent.phase4c15_delivery',METRICS={},measure=None,DeliveryRejected=ValueError)
stub('agent.phase4c16_delivery_nlp',DeliveryNLPSession=FakeSession, DeliveryContext=Context,
     DELIVERY=__import__('re').compile(r'\b(?:delivery|delivered|shipping|shipment|late)\b',__import__('re').I),
     MONTH=__import__('re').compile(r'\b(January|February)\s+(20\d{2})\b',__import__('re').I),
     COMPARE=None, M='January|February', month_period=lambda m,y:None)
spec=importlib.util.spec_from_file_location('agent.phase4c17_delivery_compare',ROOT/'agent'/'phase4c17_delivery_compare.py')
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)

cases=[
 ('finance March compared with Feb after delivery', 'Why did revenue increase while profit decreased in March 2018 compared with February 2018?', True, False),
 ('finance from to', 'Why did revenue increase but profit drop from February to March 2018?', True, False),
 ('revenue fall', 'Did revenue decrease between January and February 2018?', True, False),
 ('review comparison', 'Compare review scores in January 2018 vs February 2018', True, False),
 ('product GMV comparison', 'Compare GMV January 2018 vs February 2018', True, False),
 ('delivery explicit', 'Compare late delivery rates January 2018 vs February 2018', True, True),
 ('delivery shipping explicit', 'How did shipping change January 2018 vs February 2018?', False, True),
 ('elliptical with delivery context', 'Compare January 2018 vs February 2018', True, True),
 ('elliptical without context', 'Compare January 2018 vs February 2018', False, False),
 ('single delivery metric', 'What is late delivery rate in January 2018?', True, False),
 ('unrelated topic', 'Tell me about revenue January 2018',True,False),
 ('unsupported unsafe question cannot trigger', None,True,False),
]
for label,question,previous,expect in cases:
    actual=module.is_comparison(question,object() if previous else None)
    assert actual is expect,(label,actual,expect)
    print('PASS:',label)
print('Checks passed: %d/%d'%(len(cases),len(cases)))
