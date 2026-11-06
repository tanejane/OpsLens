"""Offline regression for empty-period classification, no Gemini or PostgreSQL."""
import asyncio
from agent.phase4b57_nl_dynamic_finance import (
    _confirmed_empty_period, NoSourceCoverage, execute, Context,
)


def case_rows(placed=0, finance=0, days=0):
    return {'cohort': {'placed': placed}, 'finance': {'rows': finance},
            'daily': {'days': days}, 'integrity': {'financial_rows': finance}}


def main():
    checks = 0
    def check(label, test):
        nonlocal checks
        assert test, label
        checks += 1
        print('PASS:', label)

    check('confirmed empty audit counts classified', _confirmed_empty_period(case_rows()))
    check('numeric string zero supported', _confirmed_empty_period(case_rows('0','0','0')))
    check('missing cohort is not presumed empty', not _confirmed_empty_period({'finance':{'rows':0},'daily':{'days':0}}))
    check('null cohort is not presumed empty', not _confirmed_empty_period(case_rows(None,0,0)))
    check('mixed missing financial data not mislabeled', not _confirmed_empty_period(case_rows(10,0,0)))
    check('finance-only anomaly not mislabeled', not _confirmed_empty_period(case_rows(0,1,0)))
    check('daily-only anomaly not mislabeled', not _confirmed_empty_period(case_rows(0,0,1)))
    check('booleans are not accepted as counts', not _confirmed_empty_period(case_rows(False,0,0)))
    check('malformed count does not become no coverage', not _confirmed_empty_period(case_rows('abc',0,0)))

    from agent.phase4b56_dynamic_period import requested_period
    p = requested_period('2025-01-01', '2025-02-01')
    calls = []
    empty = case_rows()
    async def reader(sql, purpose):
        calls.append(purpose)
        key = purpose.split(': ')[-1]
        assert key in empty, 'Metric SQL ran despite zero coverage'
        return empty[key]
    try:
        asyncio.run(execute('effective_revenue', None, p, reader))
        raise AssertionError('Expected no coverage')
    except NoSourceCoverage as exc:
        check('zero coverage raises explicit typed error', 'NO_SOURCE_COVERAGE' in str(exc))
        check('error includes requested period', '2025-01-01' in str(exc))
    check('only four audited queries were executed', len(calls) == 4)
    check('no metric SQL executed for empty period', all('Finance period integrity:' in c for c in calls))
    saved = Context('effective_revenue','2018-04-01','2018-05-01')
    check('frozen saved context unaffected', (saved.metric_id,saved.start_date,saved.end_date_exclusive)==('effective_revenue','2018-04-01','2018-05-01'))

    # Comparison with an empty period cannot silently present a result.
    calls.clear()
    try:
        asyncio.run(execute('effective_revenue', p, requested_period('2018-03-01','2018-04-01'),reader))
        raise AssertionError('Expected no coverage')
    except NoSourceCoverage:
        pass
    check('empty comparison baseline aborts safely',len(calls)==4)
    print(f'Checks passed: {checks}/{checks}')

if __name__ == '__main__': main()
