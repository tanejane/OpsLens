"""Offline contract and tamper regression tests for 5.2D. Does not connect to PostgreSQL."""
from copy import deepcopy
from pathlib import Path
from scripts.phase5_2d_assess import assess, CohortAuditRejected, COUNTS, GLOBAL, DATES

DATES_LIST = list(DATES)

def fixture():
    months=[]
    for start,end,n in [('2018-02-01','2018-03-01',6728),('2018-03-01','2018-04-01',7211)]:
        p={'month_start':start,'month_end':end}
        p.update({key:(n if key in ('source_rows','source_unique_orders','delivery_rows','delivery_unique_orders','review_rows','review_unique_orders') else 0) for key in COUNTS})
        months.append(p)
    return {'contract':'PHASE5_2D_EXACT_ORDER_COHORT_V1','time_basis':'order_purchase_time',
            'month_pairs':months,'global_quality':{key:0 for key in GLOBAL},
            'read_only':True,'approved_for_mcp':False,'causal_claim':False}

def fails(payload):
    try:return assess(payload)['status']!='EXACT_ORDER_COHORT_RECONCILED'
    except (ValueError,TypeError,KeyError):return True

def main():
    tested=0
    def check(name,good):
        nonlocal tested
        assert good,name
        tested+=1
        print('PASS:',name)
    check('exact sample cohort success',not fails(fixture()))
    for key in GLOBAL:
        d=fixture();d['global_quality'][key]=1
        check('detect global '+key,fails(d))
    for ix in (0,1):
        for field in COUNTS[6:]:
            d=fixture();d['month_pairs'][ix][field]=1
            check(f'detect {ix} {field}',fails(d))
    for field in ['source_rows','source_unique_orders','delivery_rows','delivery_unique_orders','review_rows','review_unique_orders']:
        d=fixture();d['month_pairs'][0][field]-=1
        check('detect mismatch '+field,fails(d))
    for mutation in ['approved_for_mcp','causal_claim']:
        d=fixture();d[mutation]=True
        check('reject '+mutation,fails(d))
    d=fixture();d['read_only']=False;check('read-only enforced',fails(d))
    d=fixture();d['month_pairs'].reverse();check('reject swapped cohorts',fails(d))
    d=fixture();d['month_pairs'][0]['month_start']='2018-05-01';check('reject May cohort',fails(d))
    d=fixture();d['contract']='PHASE5_2B_EXACT_ORDER_COHORT_V1';check('reject old contract',fails(d))
    d=fixture();d['month_pairs'][0]['source_rows']=True;check('reject bool count',fails(d))
    d=fixture();d['month_pairs'][0]['source_rows']=-1;check('reject negative count',fails(d))
    d=fixture();d['month_pairs'][0]['source_rows']=0;d['month_pairs'][0]['source_unique_orders']=0;d['month_pairs'][0]['delivery_rows']=0;d['month_pairs'][0]['delivery_unique_orders']=0;d['month_pairs'][0]['review_rows']=0;d['month_pairs'][0]['review_unique_orders']=0;check('reject empty cohort',fails(d))
    d=fixture();d['month_pairs'][0]['fake']=4;check('reject extra column',fails(d))
    d=fixture();del d['global_quality'];check('reject missing quality',fails(d))
    d=fixture();d['time_basis']='delivery_time';check('purchase cohort required',fails(d))
    sql=Path(__file__).resolve().parents[1].joinpath('sql/phase5_2d_order_cohort_audit.sql').read_text()
    for fragment in ("DATE '2018-02-01'", "DATE '2018-03-01'", "DATE '2018-04-01'",'commerce.orders','semantic.order_delivery_evidence_v1','semantic.order_review_evidence_v1','EXCEPT','IS DISTINCT FROM','PHASE5_2D_EXACT_ORDER_COHORT_V1'):
        check('SQL '+fragment,fragment in sql)
    check('no write statements',not any(word in '\n'.join(line for line in sql.lower().splitlines() if not line.strip().startswith('--')) for word in ('insert into','delete from','update ','drop table','alter table','grant ')))
    print(f'Checks passed: {tested}/{tested}')

if __name__=='__main__':main()
