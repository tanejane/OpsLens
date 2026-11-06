"""Read a single JSON audit object produced by phase4c9_cx_delivery_audit.sql."""
import argparse, json
from agent.phase4c9_operational_audit import assess

def main():
    p=argparse.ArgumentParser(); p.add_argument('audit_json', help='Path to psql audit output')
    args=p.parse_args()
    with open(args.audit_json,encoding='utf-8-sig') as f: content=f.read().strip()
    # psql output should contain only the SELECT JSON object; fail if other text appears.
    audit=json.loads(content)
    result=assess(audit)
    print(json.dumps(result,indent=2))
    if result['status']=='AUDIT_BLOCKED': raise SystemExit(2)
if __name__=='__main__': main()
