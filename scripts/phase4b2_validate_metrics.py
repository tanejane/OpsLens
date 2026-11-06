from agent.phase4b2_metric_governance import METRICS,MetricRequest,compile_metric,QueryRejected

cases=0
def expect(name,fn,blocked=False):
    global cases
    try:
        result=fn()
        if blocked: raise AssertionError(f'{name}: should have been rejected')
    except QueryRejected:
        if not blocked: raise
    cases+=1; print('PASS:',name)

def run():
    cols={'revenue':'numeric','cogs':'numeric','contribution_profit':'numeric','business_date':'date'}
    allowed={'semantic.daily_commerce','commerce.orders','cx.effective_reviews','semantic.ga4_funnel_daily'}
    q=lambda metric,dimensions=[]: compile_metric(MetricRequest(metric=metric,dimensions=dimensions),cols,allowed)
    expect('Gross margin is ratio of sums',lambda: assert_contains(q('gross_margin_pct'),'SUM("revenue") - SUM("cogs")','NULLIF(SUM("revenue"),0)'))
    expect('Contribution margin is ratio of sums',lambda: assert_contains(q('contribution_margin_pct'),'SUM("contribution_profit") / NULLIF(SUM("revenue"),0)'))
    expect('Unregistered arbitrary metric refused',lambda:q('avg_effective_gross_profit'),True)
    expect('Category ranking refused without approved join',lambda:q('gross_margin_pct',['category']),True)
    expect('Seller order count refused without approved join',lambda:compile_metric(MetricRequest(metric='orders',dimensions=['seller_id']),{'order_id':'text','order_purchase_timestamp':'text'},allowed),True)
    expect('Missing numerator/denominator refused',lambda:q('checkout_abandon_rate_pct'),True)
    expect('Missing metric columns refused',lambda:compile_metric(MetricRequest(metric='gross_margin_pct'),{'revenue':'numeric','business_date':'date'},allowed),True)
    expect('Descending ranked metric allowed where dimension exists', lambda:assert_contains(compile_metric(MetricRequest(metric='orders',dimensions=['order_status'],order='desc'),{'order_id':'text','order_purchase_timestamp':'text','order_status':'text'},allowed),'ORDER BY metric_value DESC'))
    expect('Ascending ranked metric works', lambda:assert_contains(compile_metric(MetricRequest(metric='orders',dimensions=['order_status'],order='asc'),{'order_id':'text','order_purchase_timestamp':'text','order_status':'text'},allowed),'ORDER BY metric_value ASC'))
    expect('Date bounds retained', lambda:assert_contains(compile_metric(MetricRequest(metric='orders',start_date='2018-06-01',end_date_exclusive='2018-07-01'),{'order_id':'text','order_purchase_timestamp':'text'},allowed),"DATE '2018-06-01'","DATE '2018-07-01'"))
    print(f'Checks passed: {cases}/{cases}')
def assert_contains(value,*parts):
    for p in parts: assert p in value,(p,value)
if __name__=='__main__': run()
