import json,sys
from pathlib import Path
from agent.phase4c10_contract import assess
raw=Path(sys.argv[1]).read_text(encoding='utf-8-sig')
proof=json.loads(next(x for x in raw.splitlines() if x.lstrip().startswith('{')))
result=assess(proof)
print(json.dumps(result,indent=2))
if result['failures']:sys.exit(1)
