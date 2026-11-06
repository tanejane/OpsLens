from agent.phase4b5_semantic_expansion import audit_catalog,assess_candidates,formula_references

def main():
    checks = []
    def check(name, okay):
        assert okay, name
        checks.append(name)
        print('PASS:',name)
    catalog = {'metrics':[{'metric_name':'orders','domain':'commerce','source_view':'semantic.daily_commerce','formula':'COUNT(DISTINCT order_id)','time_field':'business_date'},
                          {'metric_name':'margin','domain':'finance','source_view':'semantic.daily_commerce','formula':'SUM(revenue) / NULLIF(SUM(cogs),0)','time_field':'business_date'}]}
    audit={'sources':{'semantic.daily_commerce':{'columns_verified':True,'live_columns':['business_date','revenue','cogs','orders'],'checks':{'grain':{'status':'VERIFIED'}}}}}
    rows=audit_catalog(catalog,audit)
    check('invalid distinct order id caught', 'unknown_formula_column:order_id' in rows[0]['issues'])
    check('valid ratio columns recognized',not rows[1]['issues'])
    check('valid columns never auto-approved',not rows[1]['execution_approved'])
    names,err=formula_references('100 * SUM(contribution_profit) / NULLIF(SUM(revenue),0)')
    check('ratio references identified',names == {'contribution_profit','revenue'} and not err)
    _,err=formula_references('SUM(revenue); DROP TABLE orders')
    check('unsupported formula syntax flagged',bool(err))
    c={'candidates':[{'metric_id':'metric_a','domain':'finance','source':'known','required_columns':['a']},
                     {'metric_id':'metric_b','domain':'marketing','source':'unknown','required_columns':['x']},
                     {'metric_id':'metric_c','domain':'finance','source':'known','required_columns':['absent']} ]}
    report=assess_candidates(c,{'sources':{'known':{'live_columns':['a']}}})
    check('known candidate still requires review',report[0]['status']=='READY_FOR_SEMANTIC_REVIEW' and not report[0]['execution_approved'])
    check('missing source metadata disclosed',report[1]['status']=='NEEDS_SOURCE_METADATA')
    check('missing required columns disclosed',report[2]['status']=='NEEDS_COLUMN_MAPPING')
    check('all candidates fail closed',all(not x['execution_approved'] for x in report))
    print(f'Checks passed: {len(checks)}/{len(checks)}')
if __name__=='__main__':main()
