"""Offline, deterministic regression suite for Phase 4C.5."""
from copy import deepcopy
from agent.phase4c5_hypotheses import evaluate_hypotheses, HypothesisRejected

FIELDS=('refund_amount','fulfillment_cost','payment_processing_cost','marketing_cost_effective','incentive_cost_effective','other_adjustments_residual')
PERIODS={'before':['2018-02-01','2018-03-01'],'after':['2018-03-01','2018-04-01']}

def fixture():
    b=dict(zip(FIELDS, (10,20,5,10,5,0)))
    a=dict(zip(FIELDS, (20,30,5,60,15,0)))
    # Other charges 50 -> 130; rev 1000 -> 1100; cogs 500 -> 650;
    # profit 450 -> 320; changes revenue +100, COGS +150, other +80, profit -130.
    totals={'before':{'effective_revenue':1000,'effective_cogs':500,'effective_contribution_profit':450},
            'after':{'effective_revenue':1100,'effective_cogs':650,'effective_contribution_profit':320}}
    ev={metric:{w:{'source':'semantic.order_economics','period':PERIODS[w],
               'source_population_rows':10,'status':'MEASURED_WITH_SCOPE_LIMITS',
               'period_reconciliation_status':'RECONCILED_FOR_REVIEW','value':totals[w][metric]}
               for w in ('before','after')} for metric in ('effective_revenue','effective_cogs','effective_contribution_profit')}
    return {'route':'investigation','executable':True,'causal_claim':False,'periods':deepcopy(PERIODS),
            'premise':{'revenue_increased':True,'contribution_profit_decreased':True,'divergence_confirmed':True,
                       'revenue_delta':'100','contribution_profit_delta':'-130'},
            'evidence':ev,
            'findings':[{'component':'effective_revenue','delta':'100','contribution_to_profit_delta':'100'},
                        {'component':'effective_cogs','delta':'150','contribution_to_profit_delta':'-150'},
                        {'component':'other_net_charges_residual','delta':'80','contribution_to_profit_delta':'-80'}],
            'driver_discovery':{'status':'RECONCILED_COMPONENT_BREAKDOWN',
                'source':'semantic.order_cost_components','causal_claim':False,'total_other_net_charges_delta':'80',
                'period_evidence':{w:{'source':'semantic.order_cost_components','period':PERIODS[w],
                   'source_population_rows':10,'reconciliation':'RECONCILED_FOR_REVIEW','causal_claim':False,
                   'components':{k:str(v) for k,v in comps.items()}} for w,comps in [('before',b),('after',a)]},
                'components':[{'component':k,'before':str(b[k]),'after':str(a[k]),
                               'delta':str(a[k]-b[k]),'contribution_to_profit_delta':str(b[k]-a[k])} for k in FIELDS]}}

def check(name,fn,raises=False):
    try:
        fn()
        assert not raises, 'expected rejection'
    except HypothesisRejected:
        assert raises, name
    print('PASS:',name)

def assert_in(r):
    assert any(v['disposition']=='NO_MATERIAL_CHANGE' for v in r['hypotheses'])

if __name__=='__main__':
    f=fixture()
    def baseline():
        r=evaluate_hypotheses(f)
        assert r['status']=='EVIDENCE_RANKED_NOT_CAUSAL' and not r['causal_claim']
        assert r['hypotheses'][0]['hypothesis_id']=='financial_component:effective_cogs'
        assert r['hypotheses_evaluated']==7 and r['hypotheses_returned']==5
        assert r['hypotheses'][0]['disposition']=='SUPPORTS_PROFIT_PRESSURE'
    check('reconciled evidence ranked by magnitude',baseline)
    check('hypothesis budget respected',lambda: (lambda r: (r['hypotheses_returned']==2) or (_ for _ in ()).throw(AssertionError()))(evaluate_hypotheses(f,max_hypotheses=2)))
    check('zero component correctly classified', lambda: (lambda r: assert_in(r))(evaluate_hypotheses(f,max_hypotheses=7)))
    def changed(path,value):
        x=deepcopy(f); target=x
        for p in path[:-1]: target=target[p]
        target[path[-1]]=value
        return x
    cases=[
        ('incorrect profit premise',('premise','contribution_profit_delta'),'-129'),
        ('false confirmation flag',('premise','divergence_confirmed'),False),
        ('tampered cost delta',('driver_discovery','components',0,'delta'),'1000'),
        ('tampered signed impact',('driver_discovery','components',0,'contribution_to_profit_delta'),'1000'),
        ('incorrect row population',('driver_discovery','period_evidence','before','source_population_rows'),11),
        ('different source',('driver_discovery','source'),'staging.order_profitability'),
        ('missing one component',('driver_discovery','period_evidence','after','components','marketing_cost_effective'),None),
        ('nonfinite value',('driver_discovery','components',0,'delta'),'NaN'),
        ('fraudulent reconciliation',('driver_discovery','total_other_net_charges_delta'),'80.5'),
        ('false causal declaration',('driver_discovery','causal_claim'),True),
        ('unreconciled period',('driver_discovery','period_evidence','before','reconciliation'),'FAILED'),
        ('changed core profit impact',('findings',1,'contribution_to_profit_delta'),'150'),
    ]
    for name,path,value in cases:
        check(name,lambda p=path,v=value: evaluate_hypotheses(changed(p,v)),raises=True)
    def missing():
        x=deepcopy(f); x['driver_discovery']={'status':'DRIVER_EVIDENCE_UNAVAILABLE'}
        r=evaluate_hypotheses(x)
        assert r['status']=='INSUFFICIENT_GOVERNED_EVIDENCE' and r['hypotheses']==[]
    check('missing drivers fail closed',missing)
    check('invalid budget rejected',lambda:evaluate_hypotheses(f,max_hypotheses=0),raises=True)
    print('Checks passed: 17/17')
