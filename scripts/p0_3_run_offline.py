"""P0.3 regression matrix, including every P0.2 offline suite."""
from concurrent.futures import ThreadPoolExecutor
import json
import sys
from scripts.p0_2_run_offline import ROOT, jobs, run

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(run,[*jobs,('scripts.p0_3_validate',['-m','scripts.p0_3_validate'])]))
    passed=sum(item['passed'] for item in results)
    report={'scope':'Offline HTTP endpoints with mocked external boundaries; existing contract and safety regressions. No live Gemini/PostgreSQL.',
        'passed':passed,'failed':len(results)-passed,'total':len(results),'results':results}
    (ROOT/'reports/p0_3_offline_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'Offline suites: {passed}/{len(results)} passed; {len(results)-passed} failed')
    for item in results:
        if not item['passed']: print(item['suite'],item['output'])
    sys.exit(0 if passed==len(results) else 1)
