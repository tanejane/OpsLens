"""Deterministic offline checks; no external dependencies."""
from decimal import Decimal
from agent.phase4b53_eligibility import Period,queries,assess,summarize

def fixture():
    return {'cohort':{'placed':100,'placed_distinct':100,'with_items':90,'without_items':10,'represented':90,'item_missing_finance':0,'finance_missing_item':0,'canceled_missing':2,'unavailable_missing':5,'created_missing':2,'other_missing':1,'null_status_missing':0},
    'finance':{'rows':90,'unique_orders':90,'revenue':1000,'cogs':600,'profit':200},
    'daily':{'days':30,'revenue':1000,'cogs':600,'profit':200,'orders':90},
    'integrity':{'financial_rows':90,'finance_only':0,'period_mismatch':0,'no_items':0}}

def main():
    p=Period('2017-11-01','2017-12-01');checks=[]
    def test(name,condition):
        checks.append(condition);print(('PASS' if condition else 'FAIL')+': '+name)
    d=fixture();ok=assess(p,d)
    test('created and other statuses allowed as evidence not policy',ok['status']=='RECONCILED_FOR_REVIEW')
    test('full successful report never approves execution',not ok['execution_approved'] and not summarize([ok])['execution_approved'])
    test('observed population balances',ok['measurements']['orders_without_items']==10)
    test('ratio of sums',ok['measurements']['effective_contribution_margin_pct']==20.0)
    d=fixture();d['cohort']['item_missing_finance']=1
    test('item without finance detected',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['cohort']['finance_missing_item']=1
    test('finance without item detected',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['cohort']['placed_distinct']=99
    test('join fanout detected',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['integrity']['period_mismatch']=1
    test('date reassignment detected',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['daily']['profit']=210
    test('daily profit mismatch detected',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['finance']['revenue']=None
    test('null numeric blocks',assess(p,d)['status']=='INCONCLUSIVE')
    d=fixture();d['finance']['revenue']=0;d['daily']['revenue']=0
    test('zero-denominator blocks',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    d=fixture();d['finance']['rows']=0;d['finance']['unique_orders']=0;d['cohort']['represented']=0
    test('missing financial coverage blocks',assess(p,d)['status']=='DISCREPANCIES_FOUND')
    q=queries(p)
    test('no runtime staging access',all('staging.' not in x.lower() for x in q.values()))
    test('no item fanout', 'SELECT DISTINCT order_id FROM "commerce"."order_items"' in q['cohort'] and 'FROM "commerce"."order_items" i' not in q['cohort'])
    test('integrity uses pre-deduplicated item IDs', 'SELECT DISTINCT order_id FROM "commerce"."order_items"' in q['integrity'] and 'NOT EXISTS' not in q['integrity'])
    test('no repeated correlated item probes', 'EXISTS(' not in q['cohort'] and q['cohort'].count('SELECT DISTINCT order_id')==1)
    test('no unqualified cohort CTE', 'WITH cohort' not in q['cohort'] and 'FROM cohort' not in q['cohort'])
    test('fully qualified base relations', 'FROM "commerce"."orders" o' in q['cohort'] and 'JOIN "semantic"."order_economics" e' in q['cohort'])

    test('queries bounded',all('LIMIT 1' in x for x in q.values()))
    test('no mutable SQL',all(not any(t in x.upper() for t in ('INSERT INTO','UPDATE ','DELETE FROM','DROP TABLE')) for x in q.values()))
    try: Period('2017-12-01','2017-11-01');bad=False
    except ValueError:bad=True
    test('inverted period blocked',bad)
    try:Period("2017-11-01' OR 1=1",'2017-12-01');bad=False
    except ValueError:bad=True
    test('date injection blocked',bad)
    test('no-period report blocked',summarize([])['status']=='REVIEW_BLOCKED')
    print('Checks passed:',sum(checks),'/',len(checks))
    if not all(checks):raise SystemExit(1)

if __name__=='__main__':main()
