"""Validation of safe date parsing and self-contained query preparation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from agent.phase4b_playground_utils import month_window, previous_month, InvestigationUnavailable, require_identifiers

checks=[]
def check(name, ok):
    checks.append(bool(ok));print(('PASS' if ok else 'FAIL')+': '+name)
check('Explicit June month window',month_window('Why did reviews decline in June 2018?')==('2018-06-01','2018-07-01'))
check('Previous-month comparison',previous_month('2018-06-01')=='2018-05-01')
check('Year boundary',month_window('December 2017')==('2017-12-01','2018-01-01'))
try: month_window('Why did reviews decline?'); ok=False
except InvestigationUnavailable: ok=True
check('Ambiguous date blocked',ok)
try: require_identifiers(['order_id'],{'order_id','effective_review_score'},'cx.effective_reviews'); ok=False
except InvestigationUnavailable: ok=True
check('Unverified schema blocked',ok)
print(f'Checks passed: {sum(checks)}/{len(checks)}')
raise SystemExit(0 if all(checks) else 1)
