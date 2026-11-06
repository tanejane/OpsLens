"""Run the applicable offline suites; retain per-suite output and exact totals."""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
modules = ['scripts.' + path.stem for path in sorted((ROOT / 'scripts').glob('phase*validat*.py'))]
modules += ['scripts.p0_1_validate', 'scripts.p0_2_validate', 'scripts.validate_phase3a',
            'scripts.validate_phase3e_imports', 'scripts.validate_phase4a',
            'scripts.phase4c19_policy_regression', 'scripts.phase4c21_sql_regression']
jobs = [(name, ['-m', name]) for name in modules]
jobs += [('core_evaluator_offline', ['-c', 'from scripts.phase5_3_eval import run_offline; run_offline()']),
         ('incident_evaluator_offline', ['-c', 'from scripts.phase5_3b_incident_eval import validate; print(validate())'])]


def run(job):
    name, arguments = job
    try:
        result = subprocess.run([sys.executable, '-B', *arguments], cwd=ROOT, capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=120,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONIOENCODING':'utf-8'})
        output = result.stdout + result.stderr
        passed = result.returncode == 0 and not re.search(r'^FAIL(?:\b|:)', output, re.M)
        return {'suite':name, 'passed':passed, 'exit_code':result.returncode, 'output':output}
    except subprocess.TimeoutExpired:
        return {'suite':name, 'passed':False, 'exit_code':None, 'output':'TIMEOUT after 120 seconds'}


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, jobs))
    passed = sum(item['passed'] for item in results)
    report = {'scope':'Offline fixtures, captured-response replay, mocks and import/static checks. No Gemini or database calls.',
        'passed':passed, 'failed':len(results)-passed, 'total':len(results), 'results':results}
    (ROOT / 'reports/p0_2_offline_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Offline suites: {passed}/{len(results)} passed; {len(results)-passed} failed')
    for item in results:
        if not item['passed']: print(item['suite'], item['output'])
    sys.exit(0 if passed == len(results) else 1)
