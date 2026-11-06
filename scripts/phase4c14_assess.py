import json,sys
from pathlib import Path
from agent.phase4c14_delivery_audit import assess

def main():
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python -m scripts.phase4c14_assess <audit.json>')
    path=Path(sys.argv[1]); txt=path.read_text(encoding='utf-8-sig').strip()
    if not txt: raise SystemExit('Empty audit result')
    payload=json.loads(txt)
    result=assess(payload)
    print(json.dumps(result,indent=2))
    if result['failures']: raise SystemExit(1)
if __name__=='__main__':main()
